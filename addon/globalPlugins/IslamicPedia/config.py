import os
import json
import globalVars
import logHandler

try:
	import addonHandler
	addonHandler.initTranslation()
except ImportError:
	import gettext
	def _(s): return s

class Config:
	PRAYER_ORDER_WAJIB = ["Subuh", "Dzuhur", "Ashar", "Maghrib", "Isya"]
	PRAYER_ORDER_OTHER = ["Imsak", "Terbit", "Dhuha"]
	
	def __init__(self):
		self.config_path = os.path.join(globalVars.appArgs.configPath, "islamicPedia.json")
		self.data = self._load()

	def _load(self):
		defaults = {
			"city_name": "",       # Default empty to force user setup
			"latitude": 0.0,
			"longitude": 0.0,
			"calc_method": "20",   # Default Kemenag RI
			"asr_method": "0",     # Default Standard (Shafi'i)
			"notification_modes": {      # Default modes for each time (off, speech, sound, both)
				"Subuh": "speech",
				"Dzuhur": "speech",
				"Ashar": "speech",
				"Maghrib": "speech",
				"Isya": "speech",
				"Imsak": "speech",
				"Terbit": "speech",
				"Dhuha": "speech"
			},
			"audio_source": "online",    # online, offline
			"hijri_adjustment": 0,       # Hijri date adjustment (-2 to +2)
			"search_progress_mode": "beep", # Search progress indicator mode (off, speech, beep, both)
			"notification_volume": 50,      # Global notification volume (0-100)
			"notification_device": "",       # Output device name (empty = system default)
			"pre_reminder_minutes": 10,
			"pre_reminder_states": {     # Default enabled for all
				"Subuh": True,
				"Dzuhur": True,
				"Ashar": True,
				"Maghrib": True,
				"Isya": True,
				"Imsak": True,
				"Terbit": True,
				"Dhuha": True
			},
			"sound_variants": {          # Default sound filenames (Empty by default, user must choose)
				"Subuh": "",
				"Dzuhur": "",
				"Ashar": "",
				"Maghrib": "",
				"Isya": "",
				"Imsak": "",
				"Terbit": "",
				"Dhuha": ""
			}
		}
		
		if os.path.exists(self.config_path):
			try:
				with open(self.config_path, "r") as f:
					data = json.load(f)
					# Merge with defaults to ensure all keys exist
					for k, v in defaults.items():
						if k not in data:
							data[k] = v
						elif isinstance(v, dict) and isinstance(data[k], dict):
							# Merge inner dictionary keys (e.g. for new prayer times added later)
							for sub_k, sub_v in v.items():
								if sub_k not in data[k]:
									data[k][sub_k] = sub_v
					return data
			except:
				return defaults
		return defaults

	def save(self):
		try:
			# Atomic Save: Write to temp file then rename to prevent corruption on crash
			temp_path = self.config_path + ".tmp"
			with open(temp_path, "w") as f:
				json.dump(self.data, f, indent=4) # Indent for readability
			
			# Windows atomic rename (replace)
			if os.path.exists(self.config_path):
				os.replace(temp_path, self.config_path)
			else:
				os.rename(temp_path, self.config_path)
				
		except Exception as e:
			logHandler.log.warning(f"IslamicPedia: Failed to save config: {e}")
			# Clean up temp if failed
			if os.path.exists(temp_path):
				try:
					os.remove(temp_path)
				except:
					pass

	def get_calc_method(self):
		return self.data.get("calc_method", "20")

	def set_calc_method(self, val):
		self.data["calc_method"] = str(val)
		self.save()

	def get_asr_method(self):
		return self.data.get("asr_method", "0")

	def set_asr_method(self, val):
		self.data["asr_method"] = str(val)
		self.save()

	def get_coordinates(self):
		return (self.data.get("latitude", 0.0), self.data.get("longitude", 0.0))

	def set_city(self, name, lat, lon):
		self.data["city_name"] = str(name)
		self.data["latitude"] = float(lat)
		self.data["longitude"] = float(lon)
		# Clear notification state on location change
		self.data["last_notified"] = {}
		self.save()

	def set_coordinates(self, lat, lon):
		self.data["latitude"] = float(lat)
		self.data["longitude"] = float(lon)
		# Clear notification state on location change
		self.data["last_notified"] = {}
		self.save()

	def get_city_name(self):
		return self.data.get("city_name", _("Belum diatur"))

	def get_short_city_name(self):
		# Helper for Schedule/Notifications (User Request: First Part Only)
		full = self.get_city_name()
		parts = [p.strip() for p in full.split(",")]
		if parts:
			return parts[0]
		return full

	def get_last_notified(self, prayer_name):
		return self.data.get("last_notified", {}).get(prayer_name, "")

	def set_last_notified(self, prayer_name, date_str):
		if "last_notified" not in self.data:
			self.data["last_notified"] = {}
		self.data["last_notified"][prayer_name] = date_str
		self.save()

	def get_hijri_adjustment(self):
		return self.data.get("hijri_adjustment", 0)

	def set_hijri_adjustment(self, val):
		self.data["hijri_adjustment"] = int(val)
		self.save()

	def get_search_progress_mode(self):
		return self.data.get("search_progress_mode", "beep")

	def set_search_progress_mode(self, val):
		self.data["search_progress_mode"] = str(val)
		self.save()

	def get_notification_volume(self):
		return int(self.data.get("notification_volume", 50))

	def set_notification_volume(self, vol):
		self.data["notification_volume"] = int(vol)
		self.save()

	def get_notification_device(self):
		return self.data.get("notification_device", "")

	def set_notification_device(self, device_name):
		self.data["notification_device"] = str(device_name)
		self.save()
