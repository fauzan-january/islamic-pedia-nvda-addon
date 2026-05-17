import os
import json
import logHandler
import urllib.request
import threading
import wx
import ui
import gui
import nvwave

try:
	import addonHandler
	addonHandler.initTranslation()
except ImportError:
	import gettext
	def _(s): return s

class SoundManager:
	def __init__(self, config):
		self.shutdown_flag = False
		self.config = config
		self.variants_file = os.path.join(os.path.dirname(__file__), "audio_variants.json")
		# User requested to store audio cache inside the addon directory
		self.cache_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "audio"))
		self.data = self._load_variants()
		
		# Set tracking for concurrent downloads
		self.downloading_files = {}
		self._play_token_main = 0 # Tracks current main alarm requests
		self._play_token_preview = 0 # Tracks current preview requests

		# Track active waveOutOpen handle for alarm audio (allows stop() to interrupt)
		self._alarm_wav_handle = None
		self._preview_wav_handle = None
		self._alarm_wmp_handle = None
		self._preview_wmp_handle = None
		
		if not os.path.exists(self.cache_dir):
			os.makedirs(self.cache_dir)
		
		# User requested to store temp files inside the addon directory as well
		self.temp_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "temp"))
		if not os.path.exists(self.temp_dir):
			os.makedirs(self.temp_dir)
		else:
			self._clean_temp()

	def _clean_temp(self):
		# Clean up temp directory
		try:
			for f in os.listdir(self.temp_dir):
				path = os.path.join(self.temp_dir, f)
				if os.path.isfile(path):
					os.unlink(path)
		except Exception as e:
			logHandler.log.error(f"IslamicPedia: Failed to clean temp dir: {e}")

	def cleanup(self):
		self.shutdown_flag = True
		self.stop()
		# Ensure MCI is closed
		try:
			import ctypes
			ctypes.windll.winmm.mciSendStringW("close islamic_pedia_sfx", None, 0, 0)
		except Exception:
			pass
		self._clean_temp()

	def smart_cleanup(self):
		if self.shutdown_flag: return
		
		# 1. Stop preview audio (Do not stop main alarm)
		self.stop_preview()
		
		# 2. Clean Temp Directory
		self._clean_temp()
		
		# 3. Clean Audio Cache
		# Gather Whitelist from config (Normalized to lower case)
		whitelist = set()
		
		# A. System Sounds
		whitelist.add("on.mp3")
		whitelist.add("off.mp3")
		whitelist.add("on.wav") # Keep wav just in case user has them
		whitelist.add("off.wav")
		
		# B. Active Variants from Config
		variants = self.config.data.get("sound_variants", {}).values()
		for filename in variants:
			if filename:
				whitelist.add(str(filename).lower())
			
		# Refresh/Scan Directory
		try:
			for f in os.listdir(self.cache_dir):
				path = os.path.join(self.cache_dir, f)
				if os.path.isfile(path):
					# Check against whitelist (case-insensitive)
					if f.lower() not in whitelist:
						try:
							os.unlink(path)
							logHandler.log.info(f"IslamicPedia: Smart Cleanup deleted unused file: {f}")
						except Exception as e:
							logHandler.log.warning(f"IslamicPedia: Failed to delete {f}: {e}")
		except Exception as e:
			logHandler.log.error(f"IslamicPedia: Error during smart cleanup: {e}")

	def _load_variants(self):
		try:
			with open(self.variants_file, "r") as f:
				return json.load(f)
		except Exception as e:
			logHandler.log.error(f"IslamicPedia: Failed to load audio variants: {e}")
			return {}

	def get_dummy_beep(self):
		# Simple beep for pre-reminder
		import tones
		tones.beep(500, 200)

	def play(self, prayer_name, is_pre_reminder=False):
		if self.shutdown_flag: return
		
		if is_pre_reminder:
			self.get_dummy_beep()
			return

		# Determine which file to play
		variant_name = self.config.data.get("sound_variants", {}).get(prayer_name, "")
		
		# If no variant configured, skip silently (user hasn't set up audio yet)
		if not variant_name:
			logHandler.log.warning(f"IslamicPedia: No sound variant configured for {prayer_name}, skipping audio playback.")
			return
		
		# For actual playback (alarm), we expect file to be in cache
		# If not in cache, try to download valid file to cache
		self.ensure_cached(variant_name, play_after=True)

	def play_system_sound(self, filename):
		"""Plays a local system sound. Uses MCI for MP3 (overlap) or nvwave for WAV."""
		if self.shutdown_flag: return
		
		path = os.path.join(self.cache_dir, filename)
		if not os.path.exists(path):
			return

		if filename.lower().endswith(".mp3"):
			self._play_sfx_mci(path)
		else:
			# Fallback for WAV using nvwave (Interrupts)
			try:
				nvwave.playWaveFile(path)
			except Exception:
				pass

	def _play_sfx_mci(self, path):
		"""Legacy MCI Player specifically for short SFX to allow overlap with nvwave."""
		if self.shutdown_flag: return
		
		try:
			import ctypes
			mci = ctypes.windll.winmm.mciSendStringW
			alias = "islamic_pedia_sfx"
			
			# 1. Stop/Close previous SFX
			mci(f"close {alias}", None, 0, 0)
			
			# 2. Open
			cmd_open = f'open "{path}" type mpegvideo alias {alias}'
			ret = mci(cmd_open, None, 0, 0)
			
			if ret != 0:
				# Retry once
				mci(f"close {alias}", None, 0, 0)
				mci(cmd_open, None, 0, 0)
			
			# 3. Play (Async)
			mci(f"play {alias}", None, 0, 0)
			
		except Exception as e:
			logHandler.log.error(f"IslamicPedia: SFX Error: {e}")

	def ensure_cached(self, filename, play_after=False):
		if not filename or self.shutdown_flag: return
		
		# Give this request a token if it wants to play
		current_token = 0
		if play_after:
			self._play_token_main += 1
			current_token = self._play_token_main
		
		local_path = os.path.join(self.cache_dir, filename)
		if os.path.exists(local_path):
			if play_after: self._play_file(local_path, current_token)
			return

		if filename not in self.downloading_files:
			self.downloading_files[filename] = current_token
			threading.Thread(target=self._download_and_play, args=(filename, local_path, play_after, current_token), daemon=True).start()
		elif play_after:
			self.downloading_files[filename] = current_token


	def preview(self, filename):
		if self.shutdown_flag: return False
		if not filename: return False
		
		self._play_token_preview += 1
		current_token = self._play_token_preview
		
		# 1. Persistent Cache
		cached_path = os.path.join(self.cache_dir, filename)
		if os.path.exists(cached_path):
			self._play_file(cached_path, current_token, is_preview=True)
			return True
			
		# 2. Temp Cache
		temp_path = os.path.join(self.temp_dir, filename)
		if os.path.exists(temp_path):
			self._play_file(temp_path, current_token, is_preview=True)
			return True
		
		# 3. Download to Temp (downloads same queue, playback flagged as preview)
		if filename not in self.downloading_files:
			self.downloading_files[filename] = current_token
			import threading
			threading.Thread(target=self._download_and_play, args=(filename, temp_path, True, current_token, True), daemon=True).start()
		else:
			# Update token so that if user mashed play/stop, the final completion will match the latest token
			self.downloading_files[filename] = current_token
		return False

	def _play_file(self, path, token=None, is_preview=False):
		"""Play a notification alarm audio file or preview.
		WAV files use WinMM waveOutOpen (supports device selection + volume).
		MP3 files use MCI (supports volume only, always default device).
		"""
		if self.shutdown_flag: return
		if not os.path.exists(path): return
		
		# If a token was provided and it no longer matches the latest request (i.e., user stopped), cancel playback
		if token is not None:
			target_token = self._play_token_preview if is_preview else self._play_token_main
			if token != target_token:
				return
		
		if is_preview:
			self.stop_preview() # Only stop current preview
		else:
			self.stop_main() # Only stop main alarm

		ext = os.path.splitext(path)[1].lower()
		if ext == ".mp3":
			try:
				self._play_alarm_mci(path, is_preview)
			except Exception as e:
				logHandler.log.error(f"IslamicPedia: MCI alarm failed: {e}")
		else:
			try:
				self._play_alarm_waveout(path, is_preview)
			except Exception as e:
				logHandler.log.error(f"IslamicPedia: waveOutOpen alarm failed, trying MCI: {e}")
				try:
					self._play_alarm_mci(path, is_preview)
				except Exception as e2:
					logHandler.log.error(f"IslamicPedia: MCI fallback alarm also failed: {e2}")

	@staticmethod
	def get_waveout_devices():
		"""Enumerate WinMM audio output devices.
		Returns list of (device_id, device_name) tuples.
		device_id -1 = WAVE_MAPPER (system default).
		"""
		import ctypes
		MAXPNAMELEN = 32

		class WAVEOUTCAPSW(ctypes.Structure):
			_fields_ = [
				('wMid',           ctypes.c_ushort),
				('wPid',           ctypes.c_ushort),
				('vDriverVersion', ctypes.c_uint),
				('szPname',        ctypes.c_wchar * MAXPNAMELEN),
				('dwFormats',      ctypes.c_uint),
				('wChannels',      ctypes.c_ushort),
				('wReserved1',     ctypes.c_ushort),
				('dwSupport',      ctypes.c_uint),
			]

		winmm = ctypes.windll.winmm
		devices = []
		try:
			num = winmm.waveOutGetNumDevs()
			for i in range(num):
				caps = WAVEOUTCAPSW()
				ret = winmm.waveOutGetDevCapsW(i, ctypes.byref(caps), ctypes.sizeof(caps))
				if ret == 0:  # MMSYSERR_NOERROR
					devices.append((i, caps.szPname))
		except Exception as e:
			logHandler.log.error(f"IslamicPedia: waveOutGetDevCaps error: {e}")
		return devices

	def _get_waveout_device_id(self):
		"""Resolve user's preferred device name to a WinMM device ID.
		Returns WAVE_MAPPER constant (0xFFFFFFFF) if device not found or not set.
		"""
		WAVE_MAPPER = 0xFFFFFFFF
		device_name = self.config.get_notification_device()
		if not device_name:
			return WAVE_MAPPER
		for dev_id, dev_name in self.get_waveout_devices():
			if dev_name == device_name:
				return dev_id
		logHandler.log.warning(f"IslamicPedia: Device '{device_name}' not found, using WAVE_MAPPER")
		return WAVE_MAPPER

	def _play_alarm_waveout(self, path, is_preview=False):
		"""Play WAV alarm via WinMM waveOutOpen.
		Supports output device selection and volume control.
		Falls back to WAVE_MAPPER (system default) if preferred device not available.
		Runs audio playback in a daemon background thread so NVDA is not blocked.
		"""
		import ctypes
		import wave as wav_module
		import time

		# --- Read WAV file ---
		try:
			with wav_module.open(path, 'rb') as wf:
				n_channels      = wf.getnchannels()
				n_samples_sec   = wf.getframerate()
				bits_per_sample = wf.getsampwidth() * 8
				audio_data      = wf.readframes(wf.getnframes())
		except Exception as e:
			logHandler.log.error(f"IslamicPedia: Cannot read WAV '{path}': {e}")
			raise

		# --- WAVEFORMATEX ---
		class WAVEFORMATEX(ctypes.Structure):
			_fields_ = [
				('wFormatTag',      ctypes.c_ushort),
				('nChannels',       ctypes.c_ushort),
				('nSamplesPerSec',  ctypes.c_uint),
				('nAvgBytesPerSec', ctypes.c_uint),
				('nBlockAlign',     ctypes.c_ushort),
				('wBitsPerSample',  ctypes.c_ushort),
				('cbSize',          ctypes.c_ushort),
			]

		wfx = WAVEFORMATEX()
		wfx.wFormatTag      = 1  # WAVE_FORMAT_PCM
		wfx.nChannels       = n_channels
		wfx.nSamplesPerSec  = n_samples_sec
		wfx.wBitsPerSample  = bits_per_sample
		wfx.nBlockAlign     = n_channels * (bits_per_sample // 8)
		wfx.nAvgBytesPerSec = n_samples_sec * wfx.nBlockAlign
		wfx.cbSize          = 0

		# --- WAVEHDR ---
		# dwUser and reserved are DWORD_PTR in the Windows API (pointer-sized integer).
		# Using c_size_t is semantically correct and safe on both 32-bit and 64-bit:
		# c_size_t = 4 bytes on 32-bit, 8 bytes on 64-bit (same as DWORD_PTR / NVDA 2026.1 64-bit).
		class WAVEHDR(ctypes.Structure):
			_fields_ = [
				('lpData',          ctypes.c_char_p),
				('dwBufferLength',  ctypes.c_uint),
				('dwBytesRecorded', ctypes.c_uint),
				('dwUser',          ctypes.c_size_t),   # DWORD_PTR: pointer-sized int
				('dwFlags',         ctypes.c_uint),
				('dwLoops',         ctypes.c_uint),
				('lpNext',          ctypes.c_void_p),   # struct WAVEHDR*: pointer
				('reserved',        ctypes.c_size_t),   # DWORD_PTR: pointer-sized int
			]

		winmm       = ctypes.windll.winmm
		WAVE_MAPPER = ctypes.c_uint(0xFFFFFFFF)
		CALLBACK_NULL = 0

		# --- Resolve device ---
		dev_id_raw = self._get_waveout_device_id()
		if dev_id_raw == 0xFFFFFFFF:
			dev_id = WAVE_MAPPER
		else:
			dev_id = ctypes.c_uint(dev_id_raw)

		# --- Open device ---
		hWave = ctypes.c_void_p(0)
		ret = winmm.waveOutOpen(
			ctypes.byref(hWave), dev_id, ctypes.byref(wfx),
			0, 0, CALLBACK_NULL
		)
		if ret != 0:
			# Fallback to system default
			logHandler.log.warning(f"IslamicPedia: waveOutOpen dev {dev_id_raw} failed ({ret}), falling back to WAVE_MAPPER")
			ret = winmm.waveOutOpen(
				ctypes.byref(hWave), WAVE_MAPPER, ctypes.byref(wfx),
				0, 0, CALLBACK_NULL
			)
			if ret != 0:
				raise RuntimeError(f"IslamicPedia: waveOutOpen WAVE_MAPPER failed: MMSYSERR {ret}")

		# Record handle so stop() can interrupt
		if is_preview:
			self._preview_wav_handle = hWave
		else:
			self._alarm_wav_handle = hWave

		# --- Set volume ---
		vol      = self.config.get_notification_volume()  # 0-100
		wm_vol   = int(vol * 0xFFFF / 100)
		vol_dword = (wm_vol << 16) | wm_vol  # Both L+R channels
		winmm.waveOutSetVolume(hWave, vol_dword)

		# --- Play in background thread ---
		def _do_play():
			try:
				# Keep audio buffer alive in this thread scope
				audio_buf = ctypes.create_string_buffer(audio_data)

				hdr = WAVEHDR()
				hdr.lpData         = ctypes.cast(audio_buf, ctypes.c_char_p)
				hdr.dwBufferLength = len(audio_data)
				hdr.dwFlags        = 0
				hdr.dwLoops        = 1

				winmm.waveOutPrepareHeader(hWave, ctypes.byref(hdr), ctypes.sizeof(hdr))
				winmm.waveOutWrite(hWave, ctypes.byref(hdr), ctypes.sizeof(hdr))

				WHDR_DONE = 0x00000001
				while not (hdr.dwFlags & WHDR_DONE):
					if self.shutdown_flag:
						winmm.waveOutReset(hWave)
						break
					time.sleep(0.1)

				winmm.waveOutUnprepareHeader(hWave, ctypes.byref(hdr), ctypes.sizeof(hdr))
			except Exception as e:
				logHandler.log.error(f"IslamicPedia: waveOutOpen playback error: {e}")
			finally:
				try:
					winmm.waveOutClose(hWave)
				except Exception:
					pass
				
				if is_preview:
					self._preview_wav_handle = None
				else:
					self._alarm_wav_handle = None

		logHandler.log.info(f"IslamicPedia: waveOutOpen alarm playing '{path}' at volume {vol}%")
		import threading
		threading.Thread(target=_do_play, daemon=True).start()


	def _play_alarm_mci(self, path, is_preview=False):
		"""Play notification alarm audio with volume control.
		Prioritizes WMP COM object for independent volume control (protects NVDA app volume).
		Falls back to MCI if WMP is unavailable.
		"""
		vol = self.config.get_notification_volume()   # 0-100
		
		try:
			import comtypes.client
			wmp = comtypes.client.CreateObject("WMPlayer.OCX")
			
			# Wait for WMP to transition states before cementing volume change
			wmp.URL = path
			wmp.settings.volume = max(0, min(100, vol))
			wmp.controls.play()
			
			if is_preview:
				self._preview_wmp_handle = wmp
			else:
				self._alarm_wmp_handle = wmp
			
			logHandler.log.info(f"IslamicPedia: WMP alarm playing '{path}' at volume {vol}%")
			
			# Force volume refresh after 200ms to bypass WMP internal state resets
			import wx
			def _force_vol():
				try:
					if is_preview:
						if getattr(self, "_preview_wmp_handle", None) == wmp:
							wmp.settings.volume = max(0, min(100, self.config.get_notification_volume()))
					else:
						if getattr(self, "_alarm_wmp_handle", None) == wmp:
							wmp.settings.volume = max(0, min(100, self.config.get_notification_volume()))
				except Exception:
					pass
			wx.CallLater(200, _force_vol)
			wx.CallLater(500, _force_vol)
			
			return
		except Exception as e:
			logHandler.log.warning(f"IslamicPedia: WMP COM fallback failed ({e}), using MCI")

		import ctypes
		mci = ctypes.windll.winmm.mciSendStringW
		alias = "islamic_pedia_preview" if is_preview else "islamic_pedia_alarm"

		# 1. Close any previously playing alarm
		mci(f"close {alias}", None, 0, 0)

		# 2. Determine device type (waveaudio for .wav, mpegvideo for .mp3)
		ext = os.path.splitext(path)[1].lower()
		if ext == ".mp3":
			device_type = "mpegvideo"
		else:
			device_type = "waveaudio"

		# 3. Open the file
		cmd_open = f'open "{path}" type {device_type} alias {alias}'
		ret = mci(cmd_open, None, 0, 0)
		if ret != 0:
			# Retry once
			mci(f"close {alias}", None, 0, 0)
			ret = mci(cmd_open, None, 0, 0)
			if ret != 0:
				raise RuntimeError(f"MCI open failed with code {ret}")

		# 4. Set volume from config (MCI scale 0-1000)
		# While MCI volume can impact the master app session volume, we fallback to it
		# just in case WMP COM fails, so the user at least gets volume control.
		mci_vol = max(0, min(1000, vol * 10))
		mci(f"setaudio {alias} volume to {mci_vol}", None, 0, 0)

		# 5. Play asynchronously
		logHandler.log.info(f"IslamicPedia: MCI alarm playing '{path}' at volume {vol}%")
		mci(f"play {alias}", None, 0, 0)


	def stop(self):
		"""Stops all background audio (Main Adzan, Preview, Downloads)."""
		self._play_token_main += 1
		self._play_token_preview += 1
		self.downloading_files.clear()
		self.stop_main()
		self.stop_preview()
		
		# Stop SFX
		try:
			import ctypes
			mci = ctypes.windll.winmm.mciSendStringW
			mci("close islamic_pedia_sfx", None, 0, 0)
		except Exception:
			pass

	def stop_main(self):
		"""Stops only the main Adzan background audio."""
		try:
			import ctypes
			mci = ctypes.windll.winmm.mciSendStringW
			mci("close islamic_pedia_alarm", None, 0, 0)
			
			if getattr(self, "_alarm_wav_handle", None) is not None:
				ctypes.windll.winmm.waveOutReset(self._alarm_wav_handle)
		except Exception:
			pass

	def stop_preview(self):
		"""Stops only the Settings Dialog preview audio."""
		self._play_token_preview += 1
		# Notice: Do not clear downloading_files globally to avoid cancelling main alarm downloads
		# We just let the token rejection handle it
		try:
			if getattr(self, "_preview_wmp_handle", None) is not None:
				self._preview_wmp_handle.controls.stop()
				self._preview_wmp_handle = None
		except Exception:
			pass

		try:
			import ctypes
			mci = ctypes.windll.winmm.mciSendStringW
			mci("close islamic_pedia_preview", None, 0, 0)
			
			if getattr(self, "_preview_wav_handle", None) is not None:
				ctypes.windll.winmm.waveOutReset(self._preview_wav_handle)
		except Exception:
			pass

	def is_playing(self):
		if len(self.downloading_files) > 0:
			return True
		if getattr(self, "_alarm_wav_handle", None) is not None:
			return True
			
		try:
			wmp = getattr(self, "_alarm_wmp_handle", None)
			if wmp is not None and wmp.playState == 3: # 3 = Playing
				return True
		except Exception:
			pass
			
		# Check MCI
		try:
			import ctypes
			buf = ctypes.create_unicode_buffer(128)
			mci = ctypes.windll.winmm.mciSendStringW
			mci("status islamic_pedia_alarm mode", buf, 128, 0)
			if buf.value == "playing":
				return True
		except Exception:
			pass
			
		return False

	def is_preview_playing(self):
		if len(self.downloading_files) > 0:
			return True
			
		if getattr(self, "_preview_wav_handle", None) is not None:
			return True
			
		try:
			wmp = getattr(self, "_preview_wmp_handle", None)
			if wmp is not None and wmp.playState == 3: # 3 = Playing
				return True
		except Exception:
			pass
			
		try:
			import ctypes
			buf = ctypes.create_unicode_buffer(128)
			mci = ctypes.windll.winmm.mciSendStringW
			mci("status islamic_pedia_preview mode", buf, 128, 0)
			if buf.value == "playing":
				return True
		except Exception:
			pass
		return False

	def _finalize_download_and_play(self, filename, local_path, token, is_preview):
		try:
			self._play_file(local_path, token, is_preview)
		finally:
			self.downloading_files.pop(filename, None)

	def _download_and_play(self, filename, local_path, play_after=False, token=None, is_preview=False):
		if self.shutdown_flag:
			self.downloading_files.pop(filename, None)
			return
			
		base_url = self.data.get("base_url", "")
		if not base_url:
			self.downloading_files.pop(filename, None)
			return
			
		url = base_url + filename
		tmp_path = local_path + ".tmp"
		try:
			logHandler.log.info(f"IslamicPedia: Downloading {url} to {local_path}")
			
			import ssl
			# Create unverified context to avoid SSL errors
			ctx = ssl.create_default_context()
			ctx.check_hostname = False
			ctx.verify_mode = ssl.CERT_NONE
			
			req = urllib.request.Request(
				url, 
				headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
			)
			
			with urllib.request.urlopen(req, context=ctx, timeout=30) as response:
				total_size = response.getheader('Content-Length')
				if total_size is not None:
					total_size = int(total_size)
				
				# Get progress mode
				try:
					progress_mode = self.config.get_download_progress_mode()
				except Exception:
					progress_mode = "beep"
					
				def do_feedback(percent):
					if progress_mode in ["speech", "both"]:
						ui.message(f"{percent}%")
					if progress_mode in ["beep", "both"]:
						try:
							import tones
							# Base pitch 440, increases up to 880 at 100%
							tones.beep(int(440 + (percent * 4.4)), 50)
						except Exception:
							pass

				if self.shutdown_flag:
					return

				with open(tmp_path, "wb") as f:
					downloaded = 0
					last_percent = -1
					
					while True:
						if self.shutdown_flag:
							return
						chunk = response.read(8192)
						if not chunk:
							break
						f.write(chunk)
						downloaded += len(chunk)
						
						if total_size and is_preview:
							percent = int((downloaded / total_size) * 100)
							# Only feedback every 10% change to avoid spam
							if percent >= last_percent + 10:
								last_percent = (percent // 10) * 10
								# Call feedback on main thread to avoid NVDA core freezes
								wx.CallAfter(do_feedback, last_percent)
				
				# Rename temp to final when completely downloaded
				import os
				if os.path.exists(local_path):
					try:
						os.remove(local_path)
					except OSError:
						pass
				try:
					os.replace(tmp_path, local_path)
				except OSError:
					if os.path.exists(tmp_path):
						import shutil
						shutil.move(tmp_path, local_path)
			
			logHandler.log.info(f"IslamicPedia: Download successful. Playing: {play_after}")
			
			transfer_to_main = False
			if play_after and not self.shutdown_flag:
				try:
					latest_token = self.downloading_files.get(filename, token)
					transfer_to_main = True
					wx.CallAfter(self._finalize_download_and_play, filename, local_path, latest_token, is_preview)
				except Exception:
					pass
		except Exception as e:
			try:
				if os.path.exists(tmp_path):
					os.remove(tmp_path)
			except Exception:
				pass
			logHandler.log.error(f"IslamicPedia: Download failed for {url}: {e}")
			if play_after and not self.shutdown_flag:
				latest_token = self.downloading_files.get(filename, token)
				# Cancel error prompt if token has expired
				target_token = self._play_token_preview if is_preview else self._play_token_main
				if latest_token is not None and latest_token != target_token:
					pass
				else:
					try:
						# Translators: Error downloading audio. {e} is the error message.
						msg = _("Gagal mengunduh data audio: {e}").format(e=e)
						wx.CallAfter(gui.messageBox, msg, _("Kesalahan"), wx.OK | wx.ICON_ERROR)
					except Exception:
						pass
		finally:
			if not locals().get("transfer_to_main", False):
				self.downloading_files.pop(filename, None)
			try:
				if os.path.exists(tmp_path):
					os.remove(tmp_path)
			except Exception:
				pass
