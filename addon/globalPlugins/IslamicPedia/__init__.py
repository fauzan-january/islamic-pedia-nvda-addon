import globalPluginHandler
import ui
import gui
import wx
import logHandler

from .config import Config
from .interface import SettingsDialog
from .api import PrayerTimeAPI
from .player import SoundManager
from .background import Scheduler
from .wiki import WikiAPI
import addonHandler
import threading
import scriptHandler

try:
	addonHandler.initTranslation()
except addonHandler.AddonError:
	import gettext
	import builtins
	builtins._ = gettext.gettext

class InfoDialog(wx.Dialog):
	def __init__(self, parent, title, content, url=None):
		super().__init__(parent, title=title, size=(600, 400), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self.url = url
		self.content = content
		
		sizer = wx.BoxSizer(wx.VERTICAL)
		
		# Text Control for content (Read Only, Multiline)
		# TE_RICH2 allows for large text handling
		self.textCtrl = wx.TextCtrl(self, value=content, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
		sizer.Add(self.textCtrl, 1, wx.EXPAND | wx.ALL, 10)
		
		# Buttons
		btnSizer = wx.BoxSizer(wx.HORIZONTAL)
		
		self.btnCopy = wx.Button(self, label=_("&Salin ke Clipboard"))
		self.btnCopy.Bind(wx.EVT_BUTTON, self.onCopy)
		btnSizer.Add(self.btnCopy, 0, wx.ALL, 5)
		
		if self.url:
			self.btnOpen = wx.Button(self, label=_("&Buka di Browser"))
			self.btnOpen.Bind(wx.EVT_BUTTON, self.onOpen)
			btnSizer.Add(self.btnOpen, 0, wx.ALL, 5)
		
		self.btnClose = wx.Button(self, wx.ID_CANCEL, label=_("&Tutup"))
		btnSizer.Add(self.btnClose, 0, wx.ALL, 5)
		
		sizer.Add(btnSizer, 0, wx.ALIGN_RIGHT | wx.BOTTOM, 10)
		
		self.SetSizer(sizer)
		self.Centre()
		self.textCtrl.SetFocus()

	def onCopy(self, event):
		if wx.TheClipboard.Open():
			wx.TheClipboard.SetData(wx.TextDataObject(self.content))
			wx.TheClipboard.Close()
			ui.message(_("Teks berhasil disalin."))
		else:
			ui.message(_("Gagal menyalin."))

	def onOpen(self, event):
		import webbrowser
		webbrowser.open(self.url)


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	scriptCategory = _("Islamic Pedia")

	def __init__(self):
		super().__init__()
		self.config = Config()
		self.api = PrayerTimeAPI()
		try:
			lang = languageHandler.getLanguage()[:2]
		except Exception:
			lang = "id"
		self.wiki = WikiAPI(lang)
		
		# Dialog Locking Flag
		self.is_dialog_open = False
		
		# Initializes Audio components
		# Wrapped in try-except to prevent addon crash if something is wrong
		try:
			self.player = SoundManager(self.config)
			self.scheduler = Scheduler(self.config, self.api)
			self.scheduler.player = self.player # Inject player into scheduler
			self.scheduler.start()
		except Exception as e:
			logHandler.log.error(f"IslamicPedia: Failed to initialize Audio System: {e}")
			self.player = None
			self.scheduler = None
		
		self.switch = False
		self.commandLayerGestures = {
			"kb:b": "help",
			"kb:f1": "help",
			"kb:j": "prayerTimes",
			"kb:k": "qibla",
			"kb:m": "findMosques",
			"kb:i": "islamicPedia",
			"kb:p": "settings",
			"kb:t": "hijriDate",
			"kb:escape": "exitLayer",
			"kb:space": "stop",
		}

	def check_dialog_open(self):
		"""Checks if a dialog is already open. If so, warns user and returns False."""
		if self.is_dialog_open:
			ui.message(_("Harap tutup dialog yang sedang terbuka terlebih dahulu."))
			return False
		return True

	def getScript(self, gesture):
		if self.switch:
			# One-Shot Mode: Check for mapped command
			script_name = None
			for identifier in gesture.identifiers:
				if identifier in self.commandLayerGestures:
					script_name = "script_" + self.commandLayerGestures[identifier]
					break
			
			if script_name:
				target_script = getattr(self, script_name)
				
				# Only speak "Keluar..." if user pressed Escape (exitLayer)
				# For other commands (Qibla, Prayer), act silently (just sound) to be faster.
				should_speak = (script_name == "script_exitLayer")
				
				def _wrapped_script(gesture):
					# CRITICAL: Close layer first to prevent stuck state
					self.closeCommandsLayer(speak=should_speak)
					
					# CHECK: If command opens a dialog, check lock first
					# These scripts open dialogs: settings, islamicPedia, findMosques, help
					dialog_scripts = ["script_settings", "script_islamicPedia", "script_findMosques", "script_help"]
					if script_name in dialog_scripts:
						if not self.check_dialog_open():
							return

					if not should_speak:
						# Optimized: Reduced delay to 50ms for snappy response.
						wx.CallLater(50, target_script, gesture)
					else:
						# For Escape: Speech "Keluar" runs in closeCommandsLayer. Script does nothing.
						target_script(gesture)
						
				return _wrapped_script
			else:
				# Unmapped gesture
				self.closeCommandsLayer(speak=True)

		return globalPluginHandler.GlobalPlugin.getScript(self, gesture)

	def closeCommandsLayer(self, speak=True):
		if self.switch:
			if self.player:
				self.player.play_system_sound("off.mp3")
		
		# Speech AFTER Sound
		if speak:
			ui.message(_("Keluar dari mode Islamic Pedia."))
		self.switch = False

	@scriptHandler.script(
		description=_("Mengaktifkan mode perintah Islamic Pedia"),
		gesture="kb:NVDA+shift+i"
	)
	def script_activateCommandLayer(self, gesture):
		if not self.check_dialog_open():
			return

		if self.player:
			self.player.play_system_sound("on.mp3")
		ui.message(_("Masuk ke mode Islamic Pedia. Tekan B atau F1 untuk menampilkan bantuan."))
		self.switch = True


	def script_islamicPedia(self, gesture):
		# 1. Input Dialog
		if not self.check_dialog_open():
			return

		gui.mainFrame.prePopup()
		self.is_dialog_open = True
		try:
			dlg = wx.TextEntryDialog(gui.mainFrame, _("Masukkan topik Islami yang ingin dicari:"), _("Islamic Pedia"), "")
			res = dlg.ShowModal()
			query = dlg.GetValue().strip()
			dlg.Destroy()
		finally:
			self.is_dialog_open = False
			
		gui.mainFrame.postPopup()

		if res == wx.ID_OK:
			if not query:
				return
			
			ui.message(_("Mencari di ensiklopedia..."))
			threading.Thread(target=self._perform_wiki_search, args=(query,), daemon=True).start()

	def _perform_wiki_search(self, query):
		results = self.wiki.search(query)
		if not results:
			wx.CallAfter(ui.message, _("Maaf, topik tidak ditemukan."))
			return
		
		# Pick first result
		title = results[0]
		data = self.wiki.get_article(title)
		
		if data:
			wx.CallAfter(self._show_wiki_result, data)
		else:
			wx.CallAfter(ui.message, _("Maaf, topik tidak ditemukan atau tidak relevan dengan konteks Islami."))

	def _show_wiki_result(self, data):
		# Use Custom Dialog
		def show():
			if not self.check_dialog_open():
				return
				
			gui.mainFrame.prePopup()
			self.is_dialog_open = True
			try:
				dlg = InfoDialog(gui.mainFrame, data['title'], data['extract'], data['url'])
				dlg.ShowModal()
				dlg.Destroy()
			finally:
				self.is_dialog_open = False
				
			gui.mainFrame.postPopup()
		
		wx.CallAfter(show)

	def script_help(self, gesture):
		msg = [
			_("Bantuan dan Daftar Perintah Penggunaan Islamic Pedia"),
			"-" * 20,
			_("B atau F1: Menampilkan bantuan atau daftar perintah"),
			_("P: Membuka menu pengaturan"),
			_("J: Menampilkan jadwal sholat hari ini"),
			_("K: Menampilkan arah kiblat"),
			_("T: Menampilkan tanggal Hijriyah"),
			_("M: Mencari masjid terdekat"),
			_("I: Cari Ensiklopedia Islami"),
			_("Spasi: Menghentikan audio pengingat yang sedang berputar saat waktu telah tiba"),
			_("Esc: Keluar dari mode Islamic Pedia")
		]
		
		full_msg = "\n".join(msg)
		
		if not self.check_dialog_open():
			return

		gui.mainFrame.prePopup()
		self.is_dialog_open = True
		try:
			# Use InfoDialog instead of browseableMessage
			dlg = InfoDialog(gui.mainFrame, _("Bantuan dan Daftar Perintah Penggunaan Islamic Pedia"), full_msg)
			dlg.ShowModal()
			dlg.Destroy()
		finally:
			self.is_dialog_open = False
		
		gui.mainFrame.postPopup()

	def script_stop(self, gesture):
		# Layer already closed by getScript, so we just stop audio here.
		if self.scheduler:
			self.scheduler.stop_audio()
		
		# Fallback if scheduler is dead for some reason
		elif self.player:
			self.player.stop()
			
		ui.message(_("Audio berhenti."))

	def script_prayerTimes(self, gesture):
		lat, lon = self.config.get_coordinates()
		city_name = self.config.get_city_name()
		
		# Simple check for default coordinates (Jakarta) or un-set
		if not city_name or city_name == "Belum diatur":
			ui.message(_("Lokasi belum diatur. Silakan tekan P untuk mengatur lokasi."))
			return

		# Run in background to prevent freezing NVDA
		if getattr(self, "_is_fetching", False):
			return
		
		self._is_fetching = True
		
		# Params
		method = self.config.get_calc_method()
		school = self.config.get_asr_method()
		
		
		def fetch():
			try:
				# Updated to unpack 3 values (Hijri added)
				date_str, schedule, hijri_str = self.api.get_prayer_times(lat, lon, method, school)
				wx.CallAfter(self._on_prayer_times_fetched, date_str, schedule, hijri_str)
			finally:
				self._is_fetching = False
		
		threading.Thread(target=fetch, daemon=True).start()
		# Shortened message to prevent speech overlap (User Feedback)
		ui.message(_("Sedang memuat jadwal..."))

	def _on_prayer_times_fetched(self, date_str, schedule, hijri_str=""):
		if schedule:
			city_name = self.config.get_short_city_name()
			msg = []
			msg.append(_(f"Jadwal Sholat untuk wilayah {city_name} dan sekitarnya"))
			msg.append("-" * 20)
			
			msg.append(_("-- SHOLAT WAJIB --"))
			for k in getattr(self.config, 'PRAYER_ORDER_WAJIB', ["Subuh", "Dzuhur", "Ashar", "Maghrib", "Isya"]):
				if k in schedule:
					msg.append(f"{k}: {schedule[k]}")
			
			msg.append("") # Spacer
			msg.append(_("-- WAKTU LAINNYA --"))
			for k in getattr(self.config, 'PRAYER_ORDER_OTHER', ["Imsak", "Terbit", "Dhuha"]):
				if k in schedule:
					msg.append(f"{k}: {schedule[k]}")

			# New Dialog Logic
			full_msg = "\n".join(msg)
			
			def show_schedule():
				if not self.check_dialog_open():
					return

				gui.mainFrame.prePopup()
				self.is_dialog_open = True
				try:
					# Use InfoDialog instead of browseableMessage
					dlg = InfoDialog(gui.mainFrame, _("Jadwal Sholat Hari Ini"), full_msg)
					dlg.ShowModal()
					dlg.Destroy()
				finally:
					self.is_dialog_open = False
				
				gui.mainFrame.postPopup()

			# Small delay 300ms to avoid speech collision
			wx.CallLater(300, show_schedule)
		else:
			ui.message(_("Gagal memuat data. Mohon periksa koneksi internet."))

	def script_settings(self, gesture):
		# Optimized: Call directly since we are already on Main Thread via CallLater
		self.showSettingsDialog()

	def script_qibla(self, gesture):
		# Check if we have coordinates
		lat, lon = self.config.get_coordinates()
		
		# If coordinates are 0.0 (default/missing)
		city_name = self.config.get_city_name()
		if not city_name or city_name == "Belum diatur" or (lat == 0.0 and lon == 0.0):
			ui.message(_("Lokasi belum diatur. Silakan tekan P untuk mengatur lokasi."))
			return

		# Exact calculation based on stored coords
		self._announce_qibla(lat, lon)

	def script_hijriDate(self, gesture):
		# Try using cached Hijri date from background scheduler first
		# This makes response "instant" like Qibla (User Request)
		if getattr(self, 'scheduler', None) and getattr(self.scheduler, 'cached_hijri', None):
			ui.message(self.scheduler.cached_hijri)
			return

		# Similar threading logic as prayerTimes
		lat, lon = self.config.get_coordinates()
		city_name = self.config.get_city_name()
		
		if not city_name or city_name == "Belum diatur":
			ui.message(_("Lokasi belum diatur. Silakan tekan P untuk mengatur lokasi."))
			return

		if getattr(self, "_is_fetching", False):
			return
		
		self._is_fetching = True
		method = self.config.get_calc_method()
		school = self.config.get_asr_method()
		
		def fetch():
			try:
				date_str, schedule, hijri_str = self.api.get_prayer_times(lat, lon, method, school)
				wx.CallAfter(self._on_hijri_fetched, hijri_str)
			finally:
				self._is_fetching = False
		
		threading.Thread(target=fetch, daemon=True).start()
		# Removed "Sedang memuat..." message as per user request

	def _on_hijri_fetched(self, hijri_str):
		if hijri_str:
			logHandler.log.info(f"IslamicPedia: Manual Hijri fetch returned: {hijri_str}")
			# Delay slightly to prevent overlap (same as Qibla/Prayer)
			wx.CallLater(300, ui.message, hijri_str)
		else:
			ui.message(_("Gagal memuat tanggal Hijriyah."))

	def _announce_qibla(self, lat, lon):
		try:
			from .qibla import calculate_bearing, get_cardinal_direction
			bearing = calculate_bearing(lat, lon)
			direction = get_cardinal_direction(bearing)
			
			# "Arah Kiblat: 295 derajat (Barat Laut)."
			msg = _("Arah Kiblat: {:.0f} derajat ({}).").format(bearing, direction)
			ui.message(msg)
		except Exception as e:
			logHandler.log.error(f"IslamicPedia: Qibla calculation error: {e}")
			ui.message(_("Terjadi kesalahan dalam menghitung arah kiblat."))

	def showSettingsDialog(self):
		try:
			# Capture old city to detect change (though config handles save, we need to know to refresh scheduler)
			old_city = self.config.get_city_name()
			
			if not self.check_dialog_open():
				return

			self.is_dialog_open = True
			try:
				dlg = SettingsDialog(None, self.config, self.api, self.scheduler, self.player)
				res = dlg.ShowModal()
				dlg.Destroy()
				
				if res == wx.ID_OK:
					# If city changed, force scheduler to clear cache so it updates immediately
					new_city = self.config.get_city_name()
					if new_city != old_city:
						logHandler.log.info("IslamicPedia: City changed, clearing scheduler cache.")
						# Resetting cached_date will force _update_sequence on next tick (1 sec)
						self.scheduler.cached_date = None
						self.scheduler.cached_schedule = None
			finally:
				self.is_dialog_open = False
		except Exception as e:
			logHandler.log.error(f"IslamicPedia: Error showing settings: {e}")
			gui.messageBox(f"Error opening settings: {e}", "Kesalahan", wx.OK | wx.ICON_ERROR)



	def script_findMosques(self, gesture):
		lat, lon = self.config.get_coordinates()
		city_name = self.config.get_city_name()
		
		if not city_name or city_name == "Belum diatur" or (lat == 0.0 and lon == 0.0):
			ui.message(_("Lokasi belum diatur. Silakan tekan P untuk mengatur lokasi."))
			return

		if getattr(self, "_is_fetching_mosque", False):
			ui.message(_("Sedang mencari masjid terdekat..."))
			return
		
		self._is_fetching_mosque = True
		
		# Feedback Timer: Announce "Sedang mencari masjid terdekat..." every 1 second
		self.mosque_feedback_timer = wx.Timer()
		def feedback_tick(evt):
			ui.message(_("Sedang mencari masjid terdekat..."))
		self.mosque_feedback_timer.Bind(wx.EVT_TIMER, feedback_tick)
		self.mosque_feedback_timer.Start(1000)
		
		# Initial announcement
		ui.message(_("Sedang mencari masjid terdekat..."))
		
		def fetch():
			try:
				# Optimized: Single broad query (3km) for better stability
				radius = 3000
				found_mosques = self.api.search_mosques(lat, lon, radius)
				
				wx.CallAfter(self._on_mosques_found, found_mosques, lat, lon, radius)
			finally:
				self._is_fetching_mosque = False
				# Stop timer safely on main thread
				wx.CallAfter(self.mosque_feedback_timer.Stop)
		
		threading.Thread(target=fetch, daemon=True).start()

	def _on_mosques_found(self, mosques, my_lat, my_lon, radius=3000):
		# Safety: Stop feedback timer immediately to prevent it firing during the dialog
		if getattr(self, 'mosque_feedback_timer', None):
			self.mosque_feedback_timer.Stop()

		# Calculate distances and sort
		from .qibla import calculate_distance, get_bearing_between, get_cardinal_direction
		
		enriched = []
		for m in mosques:
			dist = calculate_distance(my_lat, my_lon, m['lat'], m['lon'])
			bearing = get_bearing_between(my_lat, my_lon, m['lat'], m['lon'])
			direction = get_cardinal_direction(bearing)
			enriched.append({
				'name': m['name'],
				'dist': dist,
				'direction': direction,
				'lat': m['lat'],
				'lon': m['lon']
			})
			
		enriched.sort(key=lambda x: x['dist'])
		enriched = enriched[:20]
		
		city_name = self.config.get_short_city_name()
		radius_km = int(radius / 1000)
		# Standardized Title (used for Dialog and Copy Header)
		# Translators: Mosque list header. {radius} in km, {city} is city name.
		dialog_title_fmt = _("DAFTAR MASJID DALAM RADIUS {radius} KM DI {city}")
		dialog_title_text = dialog_title_fmt.format(radius=radius_km, city=city_name.upper())

		# Handle Empty Results Gracefully
		if not enriched:
			if not self.check_dialog_open():
				return

			self.is_dialog_open = True
			try:
				msg = _("Maaf, tidak ditemukan masjid dalam radius {} km di sekitar Anda.\n\nApakah Anda ingin mencari via Google Maps?").format(radius_km)
				# Use custom MessageDialog to ensure "Ya/Tidak" labels
				dlg = wx.MessageDialog(gui.mainFrame, msg, _("Tidak Ditemukan"), wx.YES_NO | wx.ICON_QUESTION)
				dlg.SetYesNoLabels(_("Ya"), _("Tidak"))
				res = dlg.ShowModal()
				dlg.Destroy()
				
				if res == wx.ID_YES:
					google_search_url = f"https://www.google.com/maps/search/masjid/@{my_lat},{my_lon},15z"
					import webbrowser
					webbrowser.open(google_search_url)
			finally:
				self.is_dialog_open = False
			return

		choices = []
		self.mosque_urls = []
		
		# Option 0: Copy All
		choices.append(_("Salin semua hasil ke Clipboard"))
		self.mosque_urls.append("COPY")
		
		# Translators: Mosque list item format. {name} is mosque name, {dist} is distance, {dir} is cardinal direction.
		# Example: "Masjid Raya (2.5 km, Direction North)"
		item_fmt = _("{name} ({dist}, Arah {dir})")

		for m in enriched:
			if m['dist'] < 1.0:
				dist_str = f"{int(m['dist']*1000)} m"
			else:
				dist_str = f"{m['dist']:.1f} km"
				
			label = item_fmt.format(name=m['name'], dist=dist_str, dir=m['direction'])
			choices.append(label)
			
			url = f"https://www.google.com/maps/search/?api=1&query={m['lat']},{m['lon']}"
			self.mosque_urls.append(url)
			
		# Add Fallback: Search in Google Maps Web
		choices.append(_("Cari 'Masjid' selengkapnya di Google Maps..."))
		# URL to search "masjid" centered at user's location
		google_search_url = f"https://www.google.com/maps/search/masjid/@{my_lat},{my_lon},15z"
		self.mosque_urls.append(google_search_url)

		# Loop to keep dialog open if "Copy" is selected
		current_selection = 1 # Default to first mosque
		
		dialog_instruction = _("Tekan Enter pada nama masjid untuk melihat lokasinya di peta. Jika masjid yang dicari tidak ada, silakan pilih menu paling bawah untuk mencari via Google Maps.")
		full_msg = f"{dialog_title_text}\n\n{dialog_instruction}"
		
		if not self.check_dialog_open():
			return

		self.is_dialog_open = True
		try:
			while True:
				dlg = wx.SingleChoiceDialog(gui.mainFrame, full_msg, _("Hasil Pencarian Masjid"), choices)
				dlg.SetSelection(current_selection)
				
				if dlg.ShowModal() == wx.ID_OK:
					sel = dlg.GetSelection()
					current_selection = sel # Remember last selection
					dlg.Destroy()
					
					if sel != wx.NOT_FOUND:
						if self.mosque_urls[sel] == "COPY":
							# Generate text
							# Use EXACT SAME title as dialog
							text_lines = [dialog_title_text, "-"*len(dialog_title_text)]
							for i, m in enumerate(enriched, 1):
								if m['dist'] < 1.0:
									dist_str = f"{int(m['dist']*1000)} m"
								else:
									dist_str = f"{m['dist']:.1f} km"
								
								# Use format string for copy content too
								line = f"{i}. " + item_fmt.format(name=m['name'], dist=dist_str, dir=m['direction'])
								text_lines.append(line)
							
							full_text = "\n".join(text_lines)
							
							if wx.TheClipboard.Open():
								wx.TheClipboard.SetData(wx.TextDataObject(full_text))
								wx.TheClipboard.Close()
								ui.message(_("Daftar masjid berhasil disalin ke clipboard."))
							else:
								ui.message(_("Gagal menyalin ke clipboard."))
						else:
							import webbrowser
							webbrowser.open(self.mosque_urls[sel])
							break
				else:
					dlg.Destroy()
					break
		finally:
			self.is_dialog_open = False
	def script_exitLayer(self, gesture):
		# Layer is already closed by getScript.
		# This function just serves as a target for the Escape gesture so it consumes the key.
		pass

	def terminate(self):
		if getattr(self, 'scheduler', None):
			self.scheduler.stop_timer()
		if getattr(self, 'player', None):
			self.player.cleanup()
		if getattr(self, 'mosque_feedback_timer', None):
			self.mosque_feedback_timer.Stop()
			
		super().terminate()
