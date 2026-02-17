import wx
import datetime
import logHandler
import ui

try:
	import addonHandler
	addonHandler.initTranslation()
except ImportError:
	import gettext
	def _(s): return s

class Scheduler:
	def __init__(self, config, api_instance):
		self.config = config
		self.api = api_instance
		self.timer = wx.Timer()
		self.timer.Bind(wx.EVT_TIMER, self.on_tick)
		self.last_check_minute = -1
		self.cached_schedule = None
		self.cached_date = None
		self.cached_hijri = None
		self.hijri_today = None
		self.hijri_tomorrow = None
		self.is_updating = False
		self.notified_events = set() # Store (prayer_name, is_pre) for current minute

	def start(self):
		# Check every 1 second to ensure we catch the minute change immediately
		self.timer.Start(1000)
		logHandler.log.info("IslamicPedia: Scheduler started")

	def stop_timer(self):
		self.timer.Stop()

	def stop_audio(self):
		# Method to be called by script_stop (Space)
		# Clears immediate audio state but keeps scheduler running
		# Crucially: Does NOT stop the timer
		if hasattr(self, 'player') and self.player:
			self.player.stop()

	def refresh_config(self):
		# Called by SettingsDialog on save
		# Forces a re-check or just logs that config changed
		logHandler.log.info("IslamicPedia: Scheduler received config refresh signal.")
		# We can force an immediate check if needed, but the next minute tick will pick it up.
		# For responsiveness, we could clear the cache if location changed, 
		# but here we just ensure the method exists to prevent crash.
		
		# CRITICAL FIX: Invalidate cache to force re-fetch of schedule in case location changed
		self.cached_schedule = None
		self.cached_date = None
		self.hijri_today = None
		self.hijri_tomorrow = None
		logHandler.log.info("IslamicPedia: Cache invalidated due to config refresh.")

	def on_tick(self, event):
		# Safety wrapper to prevent Timer from dying due to unhandled exceptions
		try:
			# Simple optimization: only check if minute has changed
			now = datetime.datetime.now()
			if now.minute == self.last_check_minute:
				return
			self.last_check_minute = now.minute
			self.notified_events.clear() # Reset duplication cache every minute (New Minute = New Events)

			self.check_prayer_time(now)
		except Exception as e:
			logHandler.log.error(f"IslamicPedia: Critical error in Scheduler tick: {e}")

	def check_prayer_time(self, now):
		try:
			lat, lon = self.config.get_coordinates()
			# If no coordinates, we can't fetch schedule
			if lat == 0.0 and lon == 0.0:
				return

			today_str = now.strftime("%Y-%m-%d")
			
			# Refresh cache logic (Async)
			if self.cached_date != today_str:
				if not self.is_updating:
					self.is_updating = True
					import threading
					threading.Thread(target=self._update_sequence, args=(today_str, lat, lon), daemon=True).start()
				
				if not self.cached_schedule:
					return

			if not self.cached_schedule:
				return

			# Check Maghrib-based Hijri Switch
			# If now >= Maghrib, switch to hijri_tomorrow
			if self.hijri_tomorrow:
				maghrib_val = self.cached_schedule.get("Maghrib", "18:00")
				try:
					# Robust parsing: "18:08 (WIB)" -> "18:08"
					clean_maghrib = maghrib_val.split(" ")[0]
					mh, mm = map(int, clean_maghrib.split(":"))
					maghrib_dt = now.replace(hour=mh, minute=mm, second=0, microsecond=0)
					
					if now >= maghrib_dt:
						if self.cached_hijri != self.hijri_tomorrow:
							logHandler.log.info(f"IslamicPedia: Switching Hijri Date (Post-Maghrib). Old: {self.cached_hijri}, New: {self.hijri_tomorrow}")
							self.cached_hijri = self.hijri_tomorrow
					else:
						# If before Maghrib, ensure it's today's date (in case time went backwards? unlikely but safe)
						if self.cached_hijri != self.hijri_today:
							self.cached_hijri = self.hijri_today
				except Exception as e:
					logHandler.log.error(f"IslamicPedia: Error checking Maghrib switch: {e}")
				except:
					pass


			
			# Check pre-reminder functionality (Global Duration, Per-Prayer Toggle)
			try:
				pre_minutes = int(self.config.data.get("pre_reminder_minutes", 10))
			except ValueError:
				pre_minutes = 10
			
			for name, time_str in self.cached_schedule.items():
				# Parse schedule time
				try:
					# Clean time string (remove (WIB) etc)
					clean_time = time_str.split(" ")[0]
					parts = list(map(int, clean_time.split(":")))
					if len(parts) >= 2:
						h, m = parts[:2]
					else:
						continue
					prayer_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
				except ValueError:
					logHandler.log.warning(f"IslamicPedia: Failed to parse time '{time_str}' for {name}")
					continue

				# 1. Check Exact Time (Adzan)
				if now.hour == h and now.minute == m:
					self.trigger_notification(name, is_pre=False)
					# Continue checking other prayers (e.g. if Imsak and another event coincide, though rare)

					
				# 2. Check Pre-Reminder
				# Logic: Calculate exact target time for reminder and compare HH:MM
				# Get per-prayer enabled state
				is_pre = self.config.data.get("pre_reminder_states", {}).get(name, True)
				
				# If pre_minutes <= 0, don't trigger (and avoid timedelta logic error if any)
				if is_pre and pre_minutes > 0:
					reminder_time = prayer_dt - datetime.timedelta(minutes=pre_minutes)
					if now.hour == reminder_time.hour and now.minute == reminder_time.minute:
						self.trigger_notification(name, is_pre=True, remaining=pre_minutes)
						# Continue loop

		except Exception as e:
			logHandler.log.error(f"IslamicPedia: Critical error in check_prayer_time: {e}")

	def _update_sequence(self, today_str, lat, lon):
		try:
			method = self.config.get_calc_method()
			school = self.config.get_asr_method()
			adj = self.config.get_hijri_adjustment()
			
			# Fetch Today
			date_str, schedule, hijri_str = self.api.get_prayer_times(lat, lon, method, school, adjustment=adj)
			
			if schedule:
				self.cached_schedule = schedule
				self.cached_date = today_str
				self.hijri_today = hijri_str
				self.cached_hijri = hijri_str 
				
				logHandler.log.info(f"IslamicPedia: Schedule updated for {today_str}")

				# Check immediately in case we missed the minute tick during update
				wx.CallAfter(self.check_prayer_time, datetime.datetime.now())
				
				# Fetch Tomorrow
				try:
					# Use datetime from module scope
					tomorrow = datetime.datetime.now() + datetime.timedelta(days=1)
					_, _, hijri_next = self.api.get_prayer_times(lat, lon, method, school, adjustment=adj, for_date=tomorrow)
					self.hijri_tomorrow = hijri_next
				except Exception as e:
					logHandler.log.error(f"IslamicPedia: Failed to fetch tomorrow's Hijri: {e}")
					self.hijri_tomorrow = hijri_str # Fallback
				
				# If API returned empty for tomorrow (handled in API but returns empty string), use today's
				if not self.hijri_tomorrow:
					self.hijri_tomorrow = hijri_str
					
		except Exception as e:
			logHandler.log.error(f"IslamicPedia: Scheduler failed to update schedule: {e}")
		finally:
			self.is_updating = False

	def trigger_notification(self, prayer_name, is_pre=False, remaining=0):
		# Deduplication check: Ensure we handle each event only ONCE per minute
		# This prevents double-trigger from race condition fixes
		event_key = (prayer_name, is_pre)
		if event_key in self.notified_events:
			return
		self.notified_events.add(event_key)

		# Persistent State Check (Anti-Double Notification on Restart)
		# Only applies to the MAIN notification (is_pre=False)
		if not is_pre:
			today_str = datetime.datetime.now().strftime("%Y-%m-%d")
			last_notified_date = self.config.get_last_notified(prayer_name)
			
			if last_notified_date == today_str:
				logHandler.log.info(f"IslamicPedia: Skipping {prayer_name} (Already notified today: {today_str})")
				return
			
			# If not notified yet, proceed, and SAVE state after successful trigger
			self.config.set_last_notified(prayer_name, today_str)

		# Default to 'both' if not found
		modes = self.config.data.get("notification_modes", {})
		mode = modes.get(prayer_name, "both")
		
		# If mode is OFF, suppress EVERYTHING (including pre-reminders)
		if mode == "off":
			return
		
		logHandler.log.info(f"IslamicPedia: Triggering notification for {prayer_name} (Mode: {mode}, Pre: {is_pre})")
		
		# User requested short name for notifications
		city_name = self.config.get_short_city_name()
		
		if is_pre:
			# Translators: Pre-reminder message. {prayer} is prayer name, {city} is city name, {time} is minutes remaining.
			msg_fmt = _("Waktu {prayer} untuk wilayah {city} dan sekitarnya akan masuk dalam waktu {time} menit lagi.")
			msg = msg_fmt.format(prayer=_(prayer_name), city=city_name, time=remaining)

			logHandler.log.info(f"IslamicPedia: Pre-reminder msg: {msg}")
			# Respect modes for Pre-Reminder too
			if mode in ["speech", "both"]:
				ui.message(msg)
			
			if mode in ["sound", "both"]:
				# Pre-reminder beeps
				try:
					import tones
					tones.beep(440, 200)
					tones.beep(440, 200)
				except:
					pass
		else:
			# Differentiate message based on type
			if prayer_name in ["Subuh", "Dzuhur", "Ashar", "Maghrib", "Isya"]:
				# Translators: Adzan notification. {prayer} is prayer name, {city} is city name.
				msg_fmt = _("Waktu {prayer} telah tiba untuk wilayah {city} dan sekitarnya.")
				msg = msg_fmt.format(prayer=_(prayer_name), city=city_name)
			else:
				# For Imsak, Terbit, Dhuha
				# Translators: Other time notification. {prayer} is prayer name, {city} is city name.
				msg_fmt = _("Sekarang memasuki waktu {prayer} untuk wilayah {city} dan sekitarnya.")
				msg = msg_fmt.format(prayer=_(prayer_name), city=city_name)
			
			if mode in ["speech", "both"]:
				ui.message(msg)
			
			if mode in ["sound", "both"]:
				# Play sound via SoundManager
				if hasattr(self, 'player') and self.player:
					logHandler.log.info(f"IslamicPedia: Playing audio for {prayer_name}")
					self.player.play(prayer_name)
				else:
					logHandler.log.warning("IslamicPedia: Cannot play audio, player not found or not initialized")
