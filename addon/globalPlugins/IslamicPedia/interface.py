import wx
import gui
import ui
import logHandler
from .config import Config

try:
	import addonHandler
	addonHandler.initTranslation()
except ImportError:
	import gettext
	def _(s): return s

class SettingsDialog(wx.Dialog):
	def __init__(self, parent, config, api, scheduler=None, player=None):
		# Use resizeable dialog style
		super().__init__(parent, title=_("Pengaturan Islamic Pedia"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		
		# Prevent UI updates during construction to improve performance
		self.Freeze()
		
		self.config = config
		self.api = api
		self.scheduler = scheduler
		self.player = player
		if self.player is None:
			from .player import SoundManager
			self.player = SoundManager(self.config)

		self.mainSizer = wx.BoxSizer(wx.VERTICAL)
		self.notebook = wx.Notebook(self)
		
		# Initialize lazy loaded components to None
		self.cmb_calc = None
		self.cmb_asr = None
		self.spin_adj = None # Also for Hijri adjustment if it was lazy loaded (it is in location tab which is always loaded, but good practice)

		# === TAB 1: LOKASI (Always Load) ===
		self.page_location = wx.Panel(self.notebook)
		self.setup_location_tab()
		self.notebook.AddPage(self.page_location, _("Lokasi"))

		# === TAB 2: NOTIFIKASI (Lazy Load) ===
		# Just create empty panel, content loaded on first visit
		self.page_audio = wx.Panel(self.notebook)
		self.audio_tab_initialized = False
		self.notebook.AddPage(self.page_audio, _("Notifikasi"))

		# === TAB 3: LANJUTAN (Metode & Koreksi) ===
		self.page_method = wx.Panel(self.notebook)
		self.method_tab_initialized = False
		self.notebook.AddPage(self.page_method, _("Lanjutan"))

		# === TAB 4: DONASI (Lazy Load) ===
		self.page_donation = wx.Panel(self.notebook)
		self.donation_tab_initialized = False
		self.notebook.AddPage(self.page_donation, _("Donasi"))

		self.notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.on_tab_changed)

		self.mainSizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 5)

		# Buttons
		btnSizer = wx.BoxSizer(wx.HORIZONTAL)
		
		self.btn_ok = wx.Button(self, wx.ID_OK, label=_("OK"))
		self.btn_ok.Bind(wx.EVT_BUTTON, self.on_save)
		
		self.btn_cancel = wx.Button(self, wx.ID_CANCEL, label=_("Batal"))
		self.btn_cancel.Bind(wx.EVT_BUTTON, self.on_cancel)
		
		self.btn_apply = wx.Button(self, wx.ID_APPLY, label=_("Terapkan"))
		self.btn_apply.Bind(wx.EVT_BUTTON, self.on_apply)
		
		btnSizer.Add(self.btn_ok, 0, wx.ALL, 5)
		btnSizer.Add(self.btn_cancel, 0, wx.ALL, 5)
		btnSizer.Add(self.btn_apply, 0, wx.ALL, 5)
		
		self.mainSizer.Add(btnSizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

		self.SetSizer(self.mainSizer)
		self.mainSizer.Fit(self)
		
		# Center on screen
		self.Centre()
		
		# Re-enable UI updates
		self.Thaw()
		
		# Escape key handler
		self.Bind(wx.EVT_CHAR_HOOK, self.on_char_hook)



		self.cities_cache = []
		
		# Lazy Loading Safety: Initialize variables used in on_save
		self.variant_ctrls = {}
		self.spin_pre_dur = None

	def on_tab_changed(self, event):
		sel = event.GetSelection()
		# 0 = Location, 1 = Audio, 2 = Method, 3 = Donation
		if sel == 1 and not self.audio_tab_initialized:
			self.setup_audio_tab()
			self.audio_tab_initialized = True
		elif sel == 2 and not self.method_tab_initialized:
			self.setup_method_tab()
			self.method_tab_initialized = True
		elif sel == 3 and not self.donation_tab_initialized:
			self.setup_donation_tab()
			self.donation_tab_initialized = True
		event.Skip()

	def setup_location_tab(self):
		sizer = wx.BoxSizer(wx.VERTICAL)
		
		current_city = self.config.get_city_name()
		if not current_city:
			current_city = _("Belum diatur")
			
		# Status Location (Standard editable TextCtrl to guarantee accessibility navigation)
		lbl_info = wx.StaticText(self.page_location, label=_("Lokasi Saat Ini:"))
		sizer.Add(lbl_info, 0, wx.ALL, 5)
		
		# Regular TextCtrl styled to look like a Paragraph (No Border, Grey BG)
		# We keep it "Editable" technically so NVDA allows navigation (Arrows/Tab)
		# But we block typing via EVT_CHAR and style it to look static
		self.txt_current_location = wx.TextCtrl(self.page_location, value=current_city, style=wx.TE_MULTILINE | wx.TE_NO_VSCROLL | wx.BORDER_NONE)
		self.txt_current_location.SetName(_("Lokasi Saat Ini"))
		self.txt_current_location.SetBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DFACE))
		self.txt_current_location.Bind(wx.EVT_CHAR, self.on_readonly_char)
		
		# Min height to ensure text is visible
		self.txt_current_location.SetMinSize((-1, 24))
		
		sizer.Add(self.txt_current_location, 0, wx.EXPAND | wx.ALL, 5)

		lbl_search = wx.StaticText(self.page_location, label=_("Cari Lokasi Baru:"))
		sizer.Add(lbl_search, 0, wx.ALL, 5)
		
		self.txt_search = wx.TextCtrl(self.page_location, style=wx.TE_PROCESS_ENTER)
		self.txt_search.Bind(wx.EVT_TEXT_ENTER, self.on_search)
		sizer.Add(self.txt_search, 0, wx.EXPAND | wx.ALL, 5)

		self.btn_search = wx.Button(self.page_location, label=_("Cari"))
		self.btn_search.Bind(wx.EVT_BUTTON, self.on_search)
		sizer.Add(self.btn_search, 0, wx.ALL, 5)

		self.list_results = wx.ListBox(self.page_location)
		sizer.Add(self.list_results, 1, wx.EXPAND | wx.ALL, 5)
		
		self.page_location.SetSizer(sizer)

	def setup_method_tab(self):
		sizer = wx.BoxSizer(wx.VERTICAL)
		
		# Explaining Text
		lbl_expl = wx.StaticText(self.page_method, label=_("Pilih metode perhitungan waktu sholat yang sesuai dengan wilayah atau kebiasaan Anda."))
		lbl_expl.Wrap(500)
		sizer.Add(lbl_expl, 0, wx.ALL, 10)

		# Calculation Method
		# Data source: Aladhan API
		self.calc_methods = [
			(_("Kemenag RI (Sihat) - Indonesia"), "20"),
			(_("Muslim World League"), "3"),
			(_("Umm al-Qura University, Makkah"), "4"),
			(_("Egyptian General Authority of Survey"), "5"),
			(_("Islamic Society of North America (ISNA)"), "2"),
			(_("University of Islamic Sciences, Karachi"), "1"),
			(_("Shia Ithna-Ashari, Leva Institute, Qum"), "0"),
			(_("Gulf Region"), "8"),
			(_("Kuwait"), "9"),
			(_("Qatar"), "10"),
			(_("Majlis Ugama Islam Singapura, Singapore"), "11"),
			(_("Union Organization islamic de France"), "12"),
			(_("Diyanet Isleri Baskanligi, Turkey"), "13"),
			(_("Spiritual Administration of Muslims of Russia"), "14"),
			(_("Moonsighting Committee Worldwide (Paruh Waktu)"), "15"),
			(_("Dubai (Unofficial)"), "16"),
		]
		
		lbl_calc = wx.StaticText(self.page_method, label=_("Metode Kalkulasi (Calculation Method):"))
		sizer.Add(lbl_calc, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
		
		calc_choices = [x[0] for x in self.calc_methods]
		self.cmb_calc = wx.Choice(self.page_method, choices=calc_choices)
		
		# Set selection based on config
		curr_calc = self.config.get_calc_method()
		sel_calc = 0
		for i, v in enumerate(self.calc_methods):
			if v[1] == curr_calc:
				sel_calc = i
				break
		self.cmb_calc.SetSelection(sel_calc)
		
		sizer.Add(self.cmb_calc, 0, wx.EXPAND | wx.ALL, 10)
		
		# Juristic Method
		self.asr_methods = [
			(_("Standar (Syafi'i, Maliki, Hanbali)"), "0"),
			(_("Hanafi"), "1")
		]
		
		lbl_asr = wx.StaticText(self.page_method, label=_("Metode Juristik (Ashar):"))
		sizer.Add(lbl_asr, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
		
		asr_choices = [x[0] for x in self.asr_methods]
		self.cmb_asr = wx.Choice(self.page_method, choices=asr_choices)
		
		# Set selection
		curr_asr = self.config.get_asr_method()
		sel_asr = 0
		for i, v in enumerate(self.asr_methods):
			if v[1] == curr_asr:
				sel_asr = i
				break
		self.cmb_asr.SetSelection(sel_asr)
		
		sizer.Add(self.cmb_asr, 0, wx.EXPAND | wx.ALL, 10)

		# Hijri Date Adjustment (Moved from Location Tab)
		sb_adj = wx.StaticBoxSizer(wx.VERTICAL, self.page_method, _("Koreksi Tanggal Hijriyah (+/- hari)"))
		self.spin_adj = wx.SpinCtrl(self.page_method, min=-2, max=2, initial=self.config.get_hijri_adjustment())
		sb_adj.Add(self.spin_adj, 0, wx.ALL, 5)
		sizer.Add(sb_adj, 0, wx.EXPAND | wx.ALL, 10)
		
		self.page_method.SetSizer(sizer)

	def setup_audio_tab(self):
		sizer = wx.BoxSizer(wx.VERTICAL)
		self.scroll_audio = wx.ScrolledWindow(self.page_audio)
		self.scroll_audio.SetScrollbars(20, 20, 50, 50)
		
		# Define as instance variable so toggle_audio_options can access it
		self.sizer_scroll = wx.BoxSizer(wx.VERTICAL)

		# Pre-Reminder Settings (Global Duration)
		self.sb_pre = wx.StaticBoxSizer(wx.VERTICAL, self.scroll_audio, _("Durasi Pengingat Sebelum Masuk Waktu"))
		# self.chk_pre removed (moved to per-prayer)
		
		bs_pre_dur = wx.BoxSizer(wx.HORIZONTAL)
		lbl_pre_dur = wx.StaticText(self.scroll_audio, label=_("Durasi (menit):"))
		self.spin_pre_dur = wx.SpinCtrl(self.scroll_audio, value=str(self.config.data.get("pre_reminder_minutes", 10)), min=1, max=60)
		bs_pre_dur.Add(lbl_pre_dur, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
		bs_pre_dur.Add(self.spin_pre_dur, 0)
		self.sb_pre.Add(bs_pre_dur, 0, wx.ALL, 5)
		self.sizer_scroll.Add(self.sb_pre, 0, wx.EXPAND | wx.ALL, 5)

		# Variants Container
		self.variants_sizer = wx.BoxSizer(wx.VERTICAL)
		self.variants_data = self.player.data.get("variants", {})
		self.variant_ctrls = {}
		
		# --- GROUP 1: SHOLAT WAJIB ---
		sb_wajib = wx.StaticBoxSizer(wx.VERTICAL, self.scroll_audio, _("Sholat Wajib (5 Waktu)"))
		for prayer in Config.PRAYER_ORDER_WAJIB:
			# Map display label and category
			label = f"{_(prayer)}:"
			category = "Adzan" if prayer != "Subuh" else "Subuh" # Subuh has its own category
			self.add_variant_row(sb_wajib, label, prayer, category)
		self.variants_sizer.Add(sb_wajib, 0, wx.EXPAND | wx.ALL, 5)

		# --- GROUP 2: WAKTU LAINNYA ---
		sb_other = wx.StaticBoxSizer(wx.VERTICAL, self.scroll_audio, _("Waktu Lainnya (Sunnah/Tambahan)"))
		for prayer in Config.PRAYER_ORDER_OTHER:
			label = f"{_(prayer)}:"
			category = prayer # Imsak, Terbit, Dhuha match their category name
			self.add_variant_row(sb_other, label, prayer, category)
		self.variants_sizer.Add(sb_other, 0, wx.EXPAND | wx.ALL, 5)

		self.sizer_scroll.Add(self.variants_sizer, 0, wx.EXPAND | wx.ALL, 5)

		self.scroll_audio.SetSizer(self.sizer_scroll)
		sizer.Add(self.scroll_audio, 1, wx.EXPAND | wx.ALL, 5)
		self.page_audio.SetSizer(sizer)
		
		# Timer for playback monitoring
		self.playback_timer = wx.Timer(self)
		self.Bind(wx.EVT_TIMER, self.on_playback_timer, self.playback_timer)
		self.playing_button = None
		
		# Ensure layout is updated after lazy load
		self.page_audio.Layout()

	def add_variant_row(self, sizer, label, key, category):
		# Group Box for visual separation
		sb = wx.StaticBoxSizer(wx.VERTICAL, self.scroll_audio, label)
		
		# Row 1: Mode Selection
		bs_mode = wx.BoxSizer(wx.HORIZONTAL)
		lbl_mode = wx.StaticText(self.scroll_audio, label=_("Mode:"))
		modes = ["off", "speech", "sound", "both"]
		mode_labels = [_("Mati"), _("Hanya NVDA"), _("Hanya Suara"), _("Keduanya")]
		cmb_mode = wx.Choice(self.scroll_audio, choices=mode_labels)
		
		# Get saved mode for this specific prayer
		current_mode = self.config.data.get("notification_modes", {}).get(key, "speech") # Default speech
		try:
			cmb_mode.SetSelection(modes.index(current_mode))
		except:
			cmb_mode.SetSelection(1) # Default Speech
			
		bs_mode.Add(lbl_mode, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
		bs_mode.Add(cmb_mode, 1, wx.EXPAND)
		sb.Add(bs_mode, 0, wx.EXPAND | wx.ALL, 2)
		
		# Row 2: Pre-Reminder Checkbox
		bs_pre = wx.BoxSizer(wx.HORIZONTAL)
		chk_pre = wx.CheckBox(self.scroll_audio, label=_("Aktifkan Pengingat Sebelum Masuk Waktu"))
		# Get saved state
		is_pre_on = self.config.data.get("pre_reminder_states", {}).get(key, True) # Default True
		chk_pre.SetValue(is_pre_on)
		
		bs_pre.Add(chk_pre, 0, wx.ALL, 0)
		sb.Add(bs_pre, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 2)
		
		# Row 3: Sound Selection
		bs_sound = wx.BoxSizer(wx.HORIZONTAL)
		lbl_sound = wx.StaticText(self.scroll_audio, label=_("Suara:"))
		
		choices_dict = self.variants_data.get(category, {})
		original_keys = list(choices_dict.keys())
		# Translate keys for display
		display_names = [_(k) for k in original_keys]
		
		# Add default prompt
		prompt = _("-- Pilih Suara --")
		display_names.insert(0, prompt)
		
		cmb_sound = wx.Choice(self.scroll_audio, choices=display_names)
		
		current_file = self.config.data.get("sound_variants", {}).get(key, "")
		# Find which original key maps to this file
		current_orig_key = next((k for k, v in choices_dict.items() if v == current_file), None)
		
		if current_orig_key and current_orig_key in original_keys:
			# +1 because of prompt
			cmb_sound.SetSelection(original_keys.index(current_orig_key) + 1)
		else:
			# Default to prompt
			cmb_sound.SetSelection(0)
		
		bs_sound.Add(lbl_sound, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
		bs_sound.Add(cmb_sound, 1, wx.EXPAND)
		
		# Preview Button
		btn_test = wx.Button(self.scroll_audio, label=_("Tes"), size=(-1, -1))
		# Pass choices_dict (original) to preview
		btn_test.Bind(wx.EVT_BUTTON, lambda evt, b=btn_test, c=cmb_sound, d=choices_dict: self.on_preview_audio(b, c, d))
		bs_sound.Add(btn_test, 0, wx.LEFT, 5)
		
		sb.Add(bs_sound, 0, wx.EXPAND | wx.ALL, 2)
		
		# Store controls
		self.variant_ctrls[key] = {
			"mode": (cmb_mode, modes),
			"sound": (cmb_sound, choices_dict),
			"pre": chk_pre
		}
		
		sizer.Add(sb, 0, wx.EXPAND | wx.ALL, 5)

		# Logic to toggle visibility
		def update_visibility(evt=None):
			sel = cmb_mode.GetSelection()
			# indices: 0=off, 1=speech, 2=sound, 3=both
			is_off = (sel == 0)
			
			show_sound = (sel == 2 or sel == 3)
			show_pre = not is_off
			
			# Recursive show/hide helper
			def set_sizer_items_visible(sizer, visible):
				for child in sizer.GetChildren():
					if child.IsWindow():
						child.GetWindow().Show(visible)
					elif child.IsSizer():
						set_sizer_items_visible(child.GetSizer(), visible)
			
			set_sizer_items_visible(bs_sound, show_sound)
			sb.Show(bs_sound, show_sound)

			set_sizer_items_visible(bs_pre, show_pre)
			sb.Show(bs_pre, show_pre)
			
			self.scroll_audio.Layout()
			self.scroll_audio.FitInside() # Ensure scrollbars update
			self.page_audio.Layout()
			
		cmb_mode.Bind(wx.EVT_CHOICE, update_visibility)
		update_visibility() # Initial state

	def setup_donation_tab(self):
		pass # Logic moved to separate block to avoid context mismatch issues in replacement, 
		     # but since we are replacing add_variant_row, we stop here.
		     # Wait, I need to check where add_variant_row ends. It ends at update_visibility.
		     # setup_donation_tab is next.

	# ... (save logic needs to be patched separately or included if I expand the range)
	# The prompt asked to translate combo items AND fix save logic.
	# Save logic is at lines 605-612. add_variant_row is 198-300.
	# They are far apart. I should do TWO Replace calls.
	
	# This call is for add_variant_row ONLY.


	def setup_donation_tab(self):
		sizer = wx.BoxSizer(wx.VERTICAL)
		
		# Intro Text
		# Single Large Read-Only TextCtrl for Seamless Reading (Document Style)
		# This allows user to use Arrow Keys to read everything from Intro to Bank Details without Tabbing.
		full_text = (
			_("Mari beramal jariyah dengan cara berdonasi untuk mendukung pengembangan addon Islamic Pedia agar terus bermanfaat bagi umat!\n\n") +
			"Bank BRI (Fauzan):\n069501011391500\n\n" +
			"Bank Jago (Fauzan):\n106529506491\n\n" +
			"E-Wallet Dana/GoPay (Fauzan):\n085272368074"
		)
		
		self.txt_full_info = wx.TextCtrl(
			self.page_donation, 
			value=full_text, 
			style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2 | wx.BORDER_NONE
		)
		self.txt_full_info.SetBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DFACE))
		# self.txt_full_info.Bind(wx.EVT_CHAR, self.on_readonly_char) # Let standard navigation work freely
		sizer.Add(self.txt_full_info, 1, wx.EXPAND | wx.ALL, 10)
		
		# Copy Buttons Row (Specific Numbers)
		sb_copy = wx.StaticBoxSizer(wx.HORIZONTAL, self.page_donation, _("Salin Nomor Rekening"))
		
		btn_bri = wx.Button(self.page_donation, label=_("Salin BRI"))
		btn_bri.Bind(wx.EVT_BUTTON, lambda evt: self.copy_to_clipboard("069501011391500"))
		sb_copy.Add(btn_bri, 1, wx.RIGHT, 5)
		
		btn_jago = wx.Button(self.page_donation, label=_("Salin Jago"))
		btn_jago.Bind(wx.EVT_BUTTON, lambda evt: self.copy_to_clipboard("106529506491"))
		sb_copy.Add(btn_jago, 1, wx.RIGHT, 5)

		btn_dana = wx.Button(self.page_donation, label=_("Salin Dana/GoPay"))
		btn_dana.Bind(wx.EVT_BUTTON, lambda evt: self.copy_to_clipboard("085272368074"))
		sb_copy.Add(btn_dana, 1, wx.RIGHT, 0)
		
		sizer.Add(sb_copy, 0, wx.EXPAND | wx.ALL, 10)
		

		
		# External Link Buttons
		btnSizer = wx.BoxSizer(wx.HORIZONTAL)
		
		# Saweria
		self.btn_saweria = wx.Button(self.page_donation, label=_("Donasi via Saweria"))
		self.btn_saweria.Bind(wx.EVT_BUTTON, lambda evt: self.open_url("https://saweria.co/fauzanjanuary/"))
		btnSizer.Add(self.btn_saweria, 0, wx.RIGHT, 10)
		
		# Website Donation Link
		self.btn_website = wx.Button(self.page_donation, label=_("Info Donasi Lengkap (Website)"))
		self.btn_website.Bind(wx.EVT_BUTTON, lambda evt: self.open_url("https://fauzanaja.com/berikan-dukungan/"))
		btnSizer.Add(self.btn_website, 0, wx.RIGHT, 10)
		
		sizer.Add(btnSizer, 0, wx.ALIGN_CENTER | wx.BOTTOM, 10)
		
		self.page_donation.SetSizer(sizer)
		self.page_donation.Layout()

	def on_copy_list_selection(self, event):
		sel = self.list_donation.GetSelection()
		if sel != wx.NOT_FOUND:
			item_text = self.donation_items[sel]
			# Extract number using Regex (Simple sequence of digits > 6 chars to avoid copying '2025' or short numbers if any)
			import re
			# Look for sequence of digits, allowing potential spaces or dashes if formatted, 
			# but here our format is clean digits.
			match = re.search(r':\s*(\d+)', item_text)
			if match:
				number = match.group(1)
				self.copy_to_clipboard(number)
			else:
				# Fallback: Copy pure digits if found
				match_fallback = re.search(r'(\d{8,})', item_text)
				if match_fallback:
					self.copy_to_clipboard(match_fallback.group(1))
				else:
					ui.message(_("Tidak ditemukan nomor rekening pada baris ini."))
		else:
			ui.message(_("Silakan pilih rekening terlebih dahulu."))

	def copy_to_clipboard(self, text):
		if wx.TheClipboard.Open():
			wx.TheClipboard.SetData(wx.TextDataObject(text))
			wx.TheClipboard.Close()
			ui.message(_("Info donasi berhasil disalin."))
		else:
			ui.message(_("Gagal menyalin info donasi."))

	def open_url(self, url):
		import webbrowser
		webbrowser.open(url)

	def on_char_hook(self, event):
		key = event.GetKeyCode()
		if key == wx.WXK_ESCAPE:
			self.close_and_stop()
		else:
			event.Skip()

	def on_cancel(self, event):
		self.close_and_stop()
		
	def close_and_stop(self):
		if self.player:
			self.player.smart_cleanup()
		self.EndModal(wx.ID_CANCEL)


	def on_readonly_char(self, event):
		# Block editing but allow navigation and copy
		key = event.GetKeyCode()
		
		# Allow Navigation Keys
		nav_keys = [
			wx.WXK_LEFT, wx.WXK_RIGHT, wx.WXK_UP, wx.WXK_DOWN,
			wx.WXK_HOME, wx.WXK_END, wx.WXK_PAGEUP, wx.WXK_PAGEDOWN,
			wx.WXK_TAB, wx.WXK_RETURN, wx.WXK_ESCAPE
		]
		
		if key in nav_keys:
			event.Skip()
			return
			
		# Allow Ctrl (Cmd) combinations (Ctrl+C, Ctrl+A)
		if event.ControlDown() or event.CmdDown():
			event.Skip()
			return
			
		# Block everything else (Alphanumeric typing, Backspace, Delete)
		# Just return without calling Skip() to suppress the event
		return

	def on_preview_audio(self, btn, cmb, choices):
		# Check if this button is already playing
		if self.playing_button == btn:
			# Wants to stop
			if self.player: self.player.stop()
			self.reset_playback_ui()
			return

		# If another button was playing, reset it first
		if self.playing_button:
			# Stop previous audio
			if self.player: self.player.stop()
			self.reset_playback_ui()

		sel_idx = cmb.GetSelection()
		if sel_idx > 0: # 0 is prompt
			# Map back to original key using index
			original_keys = list(choices.keys())
			if sel_idx - 1 < len(original_keys):
				orig_key = original_keys[sel_idx - 1]
				filename = choices[orig_key]
				
				if self.player:
					is_cached = self.player.preview(filename)
					
					# Update UI
					btn.SetLabel(_("Berhenti"))
					self.playing_button = btn
					
					if is_cached:
						ui.message(_("Memutar..."))
					else:
						ui.message(_("Sedang mengunduh pratinjau..."))
		elif sel_idx == 0:
			ui.message(_("Silakan pilih suara terlebih dahulu."))

	def on_playback_timer(self, event):
		# Since is_playing is unreliable for nvwave/MCI mixture without ctypes polling
		# We use a simple timeout heuristic or just let user stop it manually.
		# But to be "nice", let's auto-reset after 30 seconds max (prevent stuck button)
		# Or if we want real polling, we need ctypes. 
		# Given the constraints, we will just use a hard timeout for the button reset
		# or allow the user to click "Berhenti".
		
		# Current implementation: Auto-reset after 15 seconds (avg adzan duration preview)
		# This is a UX compromise.
		if self.playing_button:
			# Check if button still exists
			try:
				# Accessing a wx object can raise PyDeadObjectError if it's gone
				if not self.playing_button.IsBeingDeleted():
					# We can also check if thread is alive if we tracked it, but nvwave is fire-and-forget.
					# So we will just increment a counter (not implemented here) or just rely on manual stop.
					# Let's actually just disable the timer auto-stop for simplicity unless we know for sure.
					# OR: Use a simpler method: just don't auto-stop. User clicks Stop.
					pass
				else:
					self.reset_playback_ui()
			except wx.PyDeadObjectError:
				self.reset_playback_ui()
			except Exception:
				# Catch other potential errors if the button is in a bad state
				self.reset_playback_ui()


	def reset_playback_ui(self):
		self.playback_timer.Stop()
		if self.playing_button:
			try:
				self.playing_button.SetLabel(_("Dengarkan"))
				self.playing_button.Enable() # Ensure re-enabled
			except wx.PyDeadObjectError:
				# Button might have been destroyed
				pass
			except Exception:
				# Catch other potential errors if the button is in a bad state
				pass
			self.playing_button = None

	def on_search(self, event):
		query = self.txt_search.GetValue()
		if len(query) < 3:
			gui.messageBox(_("Mohon masukkan minimal 3 huruf."), _("Peringatan"), wx.OK | wx.ICON_WARNING, self)
			return
		
		self.btn_search.Disable()
		self.list_results.Clear()
		self.list_results.Append(_("Sedang mencari lokasi..."))
		self.list_results.SetFocus()
		
		import threading
		threading.Thread(target=self._do_search_thread, args=(query,), daemon=True).start()

	def _do_search_thread(self, query):
		results = self.api.search_city(query)
		wx.CallAfter(self._on_search_complete, results)

	def _on_search_complete(self, results):
		try:
			if not self or not self.btn_search:
				return
			
			self.btn_search.Enable()
			self.list_results.Clear()
			
			if results:
				# Limit results to 50 to prevent UI freeze
				MAX_RESULTS = 50
				self.cities_cache = results[:MAX_RESULTS]
				
				for city in self.cities_cache:
					self.list_results.Append(city["name"])
				
				if len(results) > MAX_RESULTS:
					self.list_results.Append(_("... Hasil terlalu banyak. Mohon ketik nama lokasi lebih lengkap ..."))
					
				self.list_results.SetSelection(0)
				self.list_results.SetFocus()
			else:
				self.cities_cache = []
				gui.messageBox(_("Lokasi tidak ditemukan."), _("Informasi"), wx.OK | wx.ICON_INFORMATION, self)
		except (RuntimeError, wx.PyDeadObjectError):
			pass

	def on_apply(self, event):
		self._save_settings(show_confirmation=True, close_dialog=False)

	def on_save(self, event):
		self._save_settings(show_confirmation=False, close_dialog=True)
		
	def _save_settings(self, show_confirmation=False, close_dialog=True):
		# VALIDATION: Check for missing sound files when sound mode is active
		errors = []
		for key, ctrls in self.variant_ctrls.items():
			# Check Mode
			cmb_mode, modes = ctrls["mode"]
			mode_sel = cmb_mode.GetSelection()
			if mode_sel != wx.NOT_FOUND:
				selected_mode = modes[mode_sel] # "off", "speech", "sound", "both"
				
				if selected_mode in ["sound", "both"]:
					# Check Sound
					cmb_sound, choices = ctrls["sound"]
					sound_sel = cmb_sound.GetSelection()
					# sound_sel == 0 is "-- Pilih Suara --" (Empty)
					if sound_sel == 0 or sound_sel == wx.NOT_FOUND:
						errors.append(key)
						
		if errors:
			msg = _("Peringatan: Anda memilih mode Suara/Keduanya untuk waktu berikut, tapi belum memilih file suaranya:\n\n")
			msg += "\n".join(errors)
			msg += _("\n\nMohon pilih suara terlebih dahulu agar notifikasi berjalan normal.")
			gui.messageBox(msg, _("Konfigurasi Belum Lengkap"), wx.OK | wx.ICON_WARNING, self)
			return

		# 1. Save Pre-Reminder Duration (Global)
		if self.spin_pre_dur:
			self.config.data["pre_reminder_minutes"] = self.spin_pre_dur.GetValue()
			
		# Save Hijri Adjustment
		if self.spin_adj:
			self.config.set_hijri_adjustment(self.spin_adj.GetValue())

		# Save Calculation Method
		if self.cmb_calc:
			sel = self.cmb_calc.GetSelection()
			if sel != wx.NOT_FOUND:
				self.config.set_calc_method(self.calc_methods[sel][1])

		# Save Juristic Method
		if self.cmb_asr:
			sel = self.cmb_asr.GetSelection()
			if sel != wx.NOT_FOUND:
				self.config.set_asr_method(self.asr_methods[sel][1])
		
		# 2. Save Variants, Modes, and Pre-Reminder Toggles
		for key, ctrls in self.variant_ctrls.items():
			cmb_mode, modes = ctrls["mode"]
			# Save Mode
			sel_mode_idx = cmb_mode.GetSelection()
			if sel_mode_idx != wx.NOT_FOUND:
				self.config.data.setdefault("notification_modes", {})[key] = modes[sel_mode_idx]
				
			# Save Sound Variant
			cmb_sound, choices_dict = ctrls["sound"]
			sel_sound_idx = cmb_sound.GetSelection()
			if sel_sound_idx > 0: # 0 is prompt "-- Pilih Suara --"
				# Index in original keys is sel - 1 (because prompt is at 0)
				original_keys = list(choices_dict.keys())
				if sel_sound_idx - 1 < len(original_keys):
					orig_key = original_keys[sel_sound_idx - 1]
					filename = choices_dict[orig_key]
					if filename:
						self.config.data.setdefault("sound_variants", {})[key] = filename
			else:
				# If prompt selected or nothing selected, maybe clear it? 
				# For now, keep existing or do nothing.
				pass
			
			# Save Pre-Reminder State
			chk_pre = ctrls["pre"]
			is_pre_on = chk_pre.GetValue()
			self.config.data.setdefault("pre_reminder_states", {})[key] = is_pre_on

		# 3. Save Location (Restored Original Logic: Save on OK)
		# Only save logic here, no immediate handlers.
		location_msg = None
		sel = self.list_results.GetSelection()
		if self.cities_cache and sel != wx.NOT_FOUND and sel < len(self.cities_cache):
			city_data = self.cities_cache[sel]
			new_city = city_data["name"]
			if new_city != self.config.get_city_name():
				self.config.set_city(new_city, city_data["lat"], city_data["lon"])
				# Helper for short name
				short_name = new_city.split(",")[0]
				location_msg = _("Lokasi berhasil diatur ke {}.").format(short_name)

		# Final Commit
		self.config.save()
		
		# Update Scheduler if active
		if self.scheduler:
			wx.CallAfter(self.scheduler.refresh_config)
			
		if location_msg:
			ui.message(location_msg)
		elif show_confirmation:
			ui.message(_("Pengaturan disimpan."))
			
		if close_dialog:
			self.close_and_stop()
		
		if self.player:
			# Stop preview and perform smart cleanup (delete unused files)
			self.player.smart_cleanup()
			
			import threading
			# Ensure selected files are cached (Downloaded permanently) in background
			def sync_cache_bg():
				# Safe access using .get in case keys missing
				variants = self.config.data.get("sound_variants", {})
				for filename in variants.values():
					if filename:
						self.player.ensure_cached(filename, play_after=False)
			threading.Thread(target=sync_cache_bg, daemon=True).start()
