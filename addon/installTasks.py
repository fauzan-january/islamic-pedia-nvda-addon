# -*- coding: utf-8 -*-
# Islamic Pedia Install Tasks
# Copyright (C) 2026 Fauzan January
# Released under GPL 2

import addonHandler
import gui
import os
import threading
import wx
import webbrowser
import ui

try:
	import languageHandler
except ImportError:
	languageHandler = None

addonHandler.initTranslation()

WHATS_NEW_FILENAME = "whats-new.txt"

def _get_whats_new_path():
	addon_dir = os.path.dirname(__file__)
	candidates = []
	if languageHandler:
		lang = languageHandler.getLanguage()
		if lang:
			candidates.append(os.path.join(addon_dir, "doc", lang, WHATS_NEW_FILENAME))
			if "_" in lang:
				candidates.append(os.path.join(addon_dir, "doc", lang.split("_", 1)[0], WHATS_NEW_FILENAME))
	
	# Fallback to root (where we put it)
	candidates.append(os.path.join(addon_dir, WHATS_NEW_FILENAME))
	
	for path in candidates:
		if os.path.isfile(path):
			return path
	return None

def _load_whats_new_text():
	path = _get_whats_new_path()
	if not path:
		return _("Informasi fitur baru tidak tersedia.")
	try:
		with open(path, "r", encoding="utf-8") as handle:
			text = handle.read().strip()
	except Exception:
		return _("Gagal memuat informasi fitur baru.")
	if not text:
		return _("Informasi fitur baru kosong.")
	return text

class WhatsNewDialog(wx.Dialog):
	def __init__(self, parent):
		super().__init__(parent, title=_("Islamic Pedia - Fitur Baru"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		main_sizer = wx.BoxSizer(wx.VERTICAL)
		
		whats_new_text = _load_whats_new_text()
		info_text = wx.TextCtrl(
			self,
			value=whats_new_text,
			style=wx.TE_MULTILINE | wx.TE_READONLY | wx.BORDER_SUNKEN | wx.TE_RICH2,
			size=(600, 400),
		)
		info_text.SetFocus()
		main_sizer.Add(info_text, 1, wx.ALL | wx.EXPAND, 15)
		
		ok_btn = wx.Button(self, wx.ID_OK, label=_("&Tutup"))
		ok_btn.SetDefault()
		main_sizer.Add(ok_btn, 0, wx.ALIGN_RIGHT | wx.ALL, 15)
		
		self.SetSizer(main_sizer)
		self.Centre()
		self.Bind(wx.EVT_BUTTON, self._on_close, ok_btn)

	def _on_close(self, evt):
		self.EndModal(wx.ID_OK)

class DonationDialog(wx.Dialog):
	def __init__(self, parent):
		super().__init__(parent, title=_("Dukung Pengembangan Islamic Pedia"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER, size=(600, 500))
		
		sizer = wx.BoxSizer(wx.VERTICAL)
		
		# Intro Text
		full_text = (
			_("Mari beramal jariyah dengan cara berdonasi untuk mendukung pengembangan addon Islamic Pedia agar terus bermanfaat bagi umat!\n\n") +
			"Bank BRI (Fauzan):\n069501011391500\n\n" +
			"Bank Jago (Fauzan):\n106529506491\n\n" +
			"E-Wallet Dana/GoPay (Fauzan):\n085272368074"
		)
		
		self.txt_full_info = wx.TextCtrl(
			self, 
			value=full_text, 
			style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2 | wx.BORDER_SUNKEN
		)
		self.txt_full_info.SetFocus()
		sizer.Add(self.txt_full_info, 1, wx.EXPAND | wx.ALL, 10)
		
		# Copy Buttons Row
		sb_copy = wx.StaticBoxSizer(wx.HORIZONTAL, self, _("Salin Nomor Rekening"))
		
		btn_bri = wx.Button(self, label=_("Salin BRI"))
		btn_bri.Bind(wx.EVT_BUTTON, lambda evt: self.copy_to_clipboard("069501011391500"))
		sb_copy.Add(btn_bri, 1, wx.RIGHT, 5)
		
		btn_jago = wx.Button(self, label=_("Salin Jago"))
		btn_jago.Bind(wx.EVT_BUTTON, lambda evt: self.copy_to_clipboard("106529506491"))
		sb_copy.Add(btn_jago, 1, wx.RIGHT, 5)

		btn_dana = wx.Button(self, label=_("Salin Dana/GoPay"))
		btn_dana.Bind(wx.EVT_BUTTON, lambda evt: self.copy_to_clipboard("085272368074"))
		sb_copy.Add(btn_dana, 1, wx.RIGHT, 0)
		
		sizer.Add(sb_copy, 0, wx.EXPAND | wx.ALL, 10)
		
		# External Link Buttons
		btnSizer = wx.BoxSizer(wx.HORIZONTAL)
		
		# Saweria
		self.btn_saweria = wx.Button(self, label=_("Donasi via Saweria"))
		self.btn_saweria.Bind(wx.EVT_BUTTON, lambda evt: self.open_url("https://saweria.co/fauzanjanuary/"))
		btnSizer.Add(self.btn_saweria, 0, wx.RIGHT, 10)
		
		# Website Donation Link
		self.btn_website = wx.Button(self, label=_("Info Donasi Lengkap (Website)"))
		self.btn_website.Bind(wx.EVT_BUTTON, lambda evt: self.open_url("https://fauzanaja.com/berikan-dukungan/"))
		btnSizer.Add(self.btn_website, 0, wx.RIGHT, 10)
		
		# Close
		self.btn_close = wx.Button(self, wx.ID_CANCEL, label=_("Tutup"))
		btnSizer.Add(self.btn_close, 0, wx.LEFT, 20)
		
		sizer.Add(btnSizer, 0, wx.ALIGN_CENTER | wx.BOTTOM, 10)
		
		self.SetSizer(sizer)
		self.Centre()

	def copy_to_clipboard(self, text):
		if wx.TheClipboard.Open():
			wx.TheClipboard.SetData(wx.TextDataObject(text))
			wx.TheClipboard.Close()
			ui.message(_("Info donasi berhasil disalin."))
		else:
			ui.message(_("Gagal menyalin info donasi."))

	def open_url(self, url):
		webbrowser.open(url)

class InstallPromptDialog(wx.Dialog):
	def __init__(self, parent):
		super().__init__(parent, title=_("Instalasi Islamic Pedia"))
		
		main_sizer = wx.BoxSizer(wx.VERTICAL)
		
		# Message
		message = _("Selamat datang di Islamic Pedia! Sebelum melanjutkan instalasi, apa yang ingin Anda lakukan?")
		text = wx.StaticText(self, label=message)
		text.Wrap(500)
		main_sizer.Add(text, 0, wx.ALL, 15)
		
		# Buttons Sizer
		btn_sizer = wx.BoxSizer(wx.VERTICAL)
		
		# 1. See What's New
		self.btn_whats_new = wx.Button(self, label=_("&1. Lihat Apa yang Baru"))
		self.btn_whats_new.Bind(wx.EVT_BUTTON, self._on_whats_new)
		btn_sizer.Add(self.btn_whats_new, 0, wx.EXPAND | wx.BOTTOM, 10)
		
		# 2. Support Development
		self.btn_support = wx.Button(self, label=_("&2. Dukung Pengembangan (Donasi)"))
		self.btn_support.Bind(wx.EVT_BUTTON, self._on_support)
		btn_sizer.Add(self.btn_support, 0, wx.EXPAND | wx.BOTTOM, 10)
		
		# 3. Continue Installation
		self.btn_continue = wx.Button(self, wx.ID_OK, label=_("&3. Lanjutkan Instalasi"))
		self.btn_continue.SetDefault()
		self.btn_continue.Bind(wx.EVT_BUTTON, self._on_continue)
		btn_sizer.Add(self.btn_continue, 0, wx.EXPAND, 0)
		
		main_sizer.Add(btn_sizer, 1, wx.EXPAND | wx.ALL, 15)
		
		self.SetSizerAndFit(main_sizer)
		self.Centre()

	def _on_whats_new(self, evt):
		dlg = WhatsNewDialog(self)
		dlg.ShowModal()
		dlg.Destroy()
		
	def _on_support(self, evt):
		# Show Donation Dialog instead of direct URL
		dlg = DonationDialog(self)
		dlg.ShowModal()
		dlg.Destroy()
			
	def _on_continue(self, evt):
		self.EndModal(wx.ID_OK)

def onInstall():
	done_event = threading.Event()

	def _show_dialog():
		gui.mainFrame.prePopup()
		try:
			prompt = InstallPromptDialog(gui.mainFrame)
			prompt.ShowModal()
			prompt.Destroy()
		finally:
			gui.mainFrame.postPopup()
			done_event.set()

	# Run GUI on main thread
	wx.CallAfter(_show_dialog)
	
	# Block installation thread until dialog closes
	done_event.wait()
