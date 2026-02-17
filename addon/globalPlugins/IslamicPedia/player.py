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
		
		local_path = os.path.join(self.cache_dir, filename)
		if os.path.exists(local_path):
			if play_after: self._play_file(local_path)
			return

		if filename not in self.downloading_files:
			self.downloading_files.add(filename)
			threading.Thread(target=self._download_and_play, args=(filename, local_path, play_after), daemon=True).start()


	def preview(self, filename):
		if self.shutdown_flag: return False
		
		if not filename: return False
		
		# 1. Persistent Cache
		cached_path = os.path.join(self.cache_dir, filename)
		if os.path.exists(cached_path):
			self._play_file(cached_path)
			return True
			
		# 2. Temp Cache
		temp_path = os.path.join(self.temp_dir, filename)
		if os.path.exists(temp_path):
			self._play_file(temp_path)
			return True
		
		# 3. Download to Temp
		# Create thread to download
		if filename not in self.downloading_files:
			self.downloading_files.add(filename)
			threading.Thread(target=self._download_and_play, args=(filename, temp_path, True), daemon=True).start()
		return False

	def _play_file(self, path):
		try:
			if self.shutdown_flag: return
			if not os.path.exists(path): return
			
			logHandler.log.info(f"IslamicPedia: Playing {path} using winsound (Async)")
			import winsound
			# SND_FILENAME | SND_ASYNC | SND_NODEFAULT
			# 0x00020000 | 0x0001 | 0x0002
			# Play Async so it doesn't block NVDA, and doesn't use NVDA's wave player channel
			winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
		except Exception as e:
			logHandler.log.error(f"IslamicPedia: Error playing file {path}: {e}")

	def stop(self):
		# Force clear download queue tracking
		self.downloading_files.clear()
		try:
			"""Hentikan audio yang sedang berjalan dengan aman."""
			import winsound
			# Stop winsound (SND_PURGE = 0x0040)
			winsound.PlaySound(None, winsound.SND_PURGE)
			
			try:
				# Cleanup legacy just in case
				if hasattr(nvwave, "fileWavePlayer") and nvwave.fileWavePlayer:
					nvwave.fileWavePlayer.stop()
				nvwave.playWaveFile(None)
			except Exception:
				pass

			# Stop MCI SFX
			import ctypes
			mci = ctypes.windll.winmm.mciSendStringW
			mci("close islamic_pedia_sfx", None, 0, 0)
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

	def _download_and_play(self, filename, local_path, play_after=False):
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
					wx.CallAfter(self._play_file, local_path)
				except Exception:
					pass
		except Exception as e:
			logHandler.log.error(f"IslamicPedia: Download failed for {url}: {e}")
			if play_after and not self.shutdown_flag:
				try:
					# Translators: Error downloading audio. {e} is the error message.
					msg = _("Gagal mengunduh data audio: {e}").format(e=e)
					wx.CallAfter(gui.messageBox, msg, _("Kesalahan"), wx.OK | wx.ICON_ERROR)
				except Exception:
					pass
		finally:
			self.downloading_files.discard(filename)
