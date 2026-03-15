import os
import json
import logHandler
import urllib.request
import threading
import wx
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
		self.downloading_files = set()
		self._play_token = 0 # Tracks current play request to prevent cancelled sounds from playing

		# Track active waveOutOpen handle for alarm audio (allows stop() to interrupt)
		self._alarm_wav_handle = None
		
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
		
		# 1. Stop audio
		self.stop()
		
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
		variant_name = self.config.data.get("sound_variants", {}).get(prayer_name, "dzami1.wav")
		
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
			self._play_token += 1
			current_token = self._play_token
		
		local_path = os.path.join(self.cache_dir, filename)
		if os.path.exists(local_path):
			if play_after: self._play_file(local_path, current_token)
			return

		if filename not in self.downloading_files:
			self.downloading_files.add(filename)
			threading.Thread(target=self._download_and_play, args=(filename, local_path, play_after, current_token), daemon=True).start()


	def preview(self, filename):
		if self.shutdown_flag: return False
		if not filename: return False
		
		self._play_token += 1
		current_token = self._play_token
		
		# 1. Persistent Cache
		cached_path = os.path.join(self.cache_dir, filename)
		if os.path.exists(cached_path):
			self._play_file(cached_path, current_token)
			return True
			
		# 2. Temp Cache
		temp_path = os.path.join(self.temp_dir, filename)
		if os.path.exists(temp_path):
			self._play_file(temp_path, current_token)
			return True
		
		# 3. Download to Temp
		if filename not in self.downloading_files:
			self.downloading_files.add(filename)
			threading.Thread(target=self._download_and_play, args=(filename, temp_path, True, current_token), daemon=True).start()
		return False

	def _play_file(self, path, token=None):
		"""Play a notification alarm audio file.
		WAV files use WinMM waveOutOpen (supports device selection + volume).
		MP3 files use MCI (supports volume only, always default device).
		"""
		if self.shutdown_flag: return
		if not os.path.exists(path): return
		
		# If a token was provided and it no longer matches the latest request (i.e., user stopped), cancel playback
		if token is not None and token != self._play_token:
			return
		
		self.stop() # Ensure previous playback is stopped

		ext = os.path.splitext(path)[1].lower()
		if ext == ".mp3":
			try:
				self._play_alarm_mci(path)
			except Exception as e:
				logHandler.log.error(f"IslamicPedia: MCI alarm failed: {e}")
		else:
			try:
				self._play_alarm_waveout(path)
			except Exception as e:
				logHandler.log.error(f"IslamicPedia: waveOutOpen alarm failed, trying MCI: {e}")
				try:
					self._play_alarm_mci(path)
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

	def _play_alarm_waveout(self, path):
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
		class WAVEHDR(ctypes.Structure):
			_fields_ = [
				('lpData',          ctypes.c_char_p),
				('dwBufferLength',  ctypes.c_uint),
				('dwBytesRecorded', ctypes.c_uint),
				('dwUser',          ctypes.c_void_p),
				('dwFlags',         ctypes.c_uint),
				('dwLoops',         ctypes.c_uint),
				('lpNext',          ctypes.c_void_p),
				('reserved',        ctypes.c_void_p),
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
				self._alarm_wav_handle = None

		logHandler.log.info(f"IslamicPedia: waveOutOpen alarm playing '{path}' at volume {vol}%")
		threading.Thread(target=_do_play, daemon=True).start()


	def _play_alarm_mci(self, path):
		"""Play notification alarm audio through MCI with volume control.
		Uses an independent alias 'islamic_pedia_alarm' that does not conflict with the SFX alias.
		MCI volume scale is 0-1000, so we multiply the user's 0-100 value by 10.
		"""
		import ctypes
		mci = ctypes.windll.winmm.mciSendStringW
		alias = "islamic_pedia_alarm"

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
		vol = self.config.get_notification_volume()   # 0-100
		mci_vol = max(0, min(1000, vol * 10))
		mci(f"setaudio {alias} volume to {mci_vol}", None, 0, 0)

		# 5. Play asynchronously
		logHandler.log.info(f"IslamicPedia: MCI alarm playing '{path}' at volume {vol}%")
		mci(f"play {alias}", None, 0, 0)


	def stop(self):
		# Force clear download queue tracking and invalidate pending play requests
		self._play_token += 1
		self.downloading_files.clear()
		try:
			# Stop active waveOutOpen alarm (WAV playback on specific device)
			try:
				import ctypes
				if self._alarm_wav_handle is not None:
					ctypes.windll.winmm.waveOutReset(self._alarm_wav_handle)
					# _alarm_wav_handle will be cleared by the background thread's finally block
			except Exception:
				pass

			# Stop winsound fallback if active
			try:
				import winsound
				winsound.PlaySound(None, winsound.SND_PURGE)
			except Exception:
				pass

			try:
				# Cleanup legacy nvwave just in case
				if hasattr(nvwave, "fileWavePlayer") and nvwave.fileWavePlayer:
					nvwave.fileWavePlayer.stop()
				nvwave.playWaveFile(None)
			except Exception:
				pass

			# Stop MCI channels (alarm MCI for MP3, sfx for effects)
			import ctypes
			mci = ctypes.windll.winmm.mciSendStringW
			mci("close islamic_pedia_sfx", None, 0, 0)
			mci("close islamic_pedia_alarm", None, 0, 0)
		except Exception as e:
			logHandler.log.error(f"IslamicPedia: Error stopping audio: {e}")

	def is_playing(self):
		# nvwave doesn't expose is_playing status easily
		# But since we use it exclusively, if we rely on it, we might not know.
		# However, for UI toggle logic, we can just assume false or track it manually if needed.
		# For now, return False as we can't reliably query PlaySound status without ctypes.
		# If user clicks "Stop", we just call stop().
		# Refactor UI to not depend on polling is_playing if possible, or just accept it's "fire and forget"
		# But wait, UI uses it to reset button label.
		# We can't easily know if PlaySound (ASYNC) is finished.
		# WE WILL RETURN FALSE to disable the auto-reset timer logic, 
		# OR we implement a heuristic/dummy.
		# Best approach: nvwave doesn't support status check.
		return False

	def _download_and_play(self, filename, local_path, play_after=False, token=None):
		if self.shutdown_flag:
			self.downloading_files.discard(filename)
			return
			
		base_url = self.data.get("base_url", "")
		if not base_url:
			self.downloading_files.discard(filename)
			return
			
		url = base_url + filename
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
				data = response.read()
				
				if self.shutdown_flag:
					return
					
				with open(local_path, "wb") as f:
					f.write(data)
			
			logHandler.log.info(f"IslamicPedia: Download successful. Playing: {play_after}")
			
			if play_after and not self.shutdown_flag:
				try:
					wx.CallAfter(self._play_file, local_path, token)
				except Exception:
					pass
		except Exception as e:
			logHandler.log.error(f"IslamicPedia: Download failed for {url}: {e}")
			if play_after and not self.shutdown_flag:
				# Cancel error prompt if token has expired
				if token is not None and token != self._play_token:
					pass
				else:
					try:
						# Translators: Error downloading audio. {e} is the error message.
						msg = _("Gagal mengunduh data audio: {e}").format(e=e)
						wx.CallAfter(gui.messageBox, msg, _("Kesalahan"), wx.OK | wx.ICON_ERROR)
					except Exception:
						pass
		finally:
			self.downloading_files.discard(filename)
