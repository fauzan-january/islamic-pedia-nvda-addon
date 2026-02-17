import urllib.request
import urllib.parse
import urllib.error
import json
import datetime
import logHandler
import time
try:
	import addonHandler
	addonHandler.initTranslation()
	import languageHandler
except ImportError:
	import gettext
	def _(s): return s
	languageHandler = None

class PrayerTimeAPI:
	# Aladhan API
	SCHEDULE_URL = "http://api.aladhan.com/v1/timings"
	# Nominatim OpenStreetMap
	SEARCH_URL = "https://nominatim.openstreetmap.org/search"
	
	def search_city(self, query):
		# Returns: list of dicts {'name': 'Display Name', 'lat': 1.23, 'lon': 4.56}
		try:
			query_encoded = urllib.parse.quote(query)
			url = f"{self.SEARCH_URL}?q={query_encoded}&format=json&limit=5&countrycodes=id"
			# Nominatim requires User-Agent
			headers = {'User-Agent': 'IslamicPedia-NVDA-Addon/1.0'}
			req = urllib.request.Request(url, headers=headers)
			
			with urllib.request.urlopen(req, timeout=10) as response:
				data = json.loads(response.read().decode())
				results = []
				for item in data:
					# Return full name as per user request (Settings keeps full name)
					full_name = item.get("display_name", _("Tidak Diketahui"))
					
					results.append({
						"name": full_name,
						"lat": float(item.get("lat", 0.0)),
						"lon": float(item.get("lon", 0.0))
					})
				return results
		except Exception as e:
			logHandler.log.error(f"IslamicPedia: Error search_city (Nominatim): {e}")
		return []

	def get_prayer_times(self, lat, lon, calc_method="20", asr_method="0", adjustment=0, for_date=None):
		# calc_method: 20 = Kemenag RI
		# asr_method: 0 = Standard (Shafi'i), 1 = Hanafi
		# adjustment: Hijri date adjustment (-2 to +2)
		
		# Timestamp used by Aladhan is UNIX timestamp
		if for_date:
			timestamp = int(for_date.timestamp())
		else:
			timestamp = int(time.time())
		
		try:
			# http://api.aladhan.com/v1/timings/{timestamp}?latitude={lat}&longitude={lon}&method={method}&school={school} (Client-size adjustment)
			url = f"{self.SCHEDULE_URL}/{timestamp}?latitude={lat}&longitude={lon}&method={calc_method}&school={asr_method}"
			
			headers = {'User-Agent': 'IslamicPedia-NVDA-Addon/1.0'}
			req = urllib.request.Request(url, headers=headers)
			
			with urllib.request.urlopen(req, timeout=15) as response:
				data = json.loads(response.read().decode())
				if data["code"] == 200:
					timings = data["data"]["timings"]
					
					# Map Aladhan keys to our internal keys
					# Aladhan: Fajr, Sunrise, Dhuhr, Asr, Sunset, Maghrib, Isha, Imsak, Midnight
					# We need: Subuh, Terbit, Dhuha, Dzuhur, Ashar, Maghrib, Isya, Imsak
					
					mapped_times = {
						"Subuh": timings["Fajr"],
						"Terbit": timings["Sunrise"],
						# Aladhan doesn't provide Dhuha explicitly usually, but some methods do?
						# Actually, Dhuha is usually Sunrise + ~20 mins. 
						# Let's see if we can calc it or if it's there. 
						# Aladhan standard doesn't return "Dhuha". We might need to calculate it manually.
						"Dzuhur": timings["Dhuhr"],
						"Ashar": timings["Asr"],
						"Maghrib": timings["Maghrib"],
						"Isya": timings["Isha"],
						"Imsak": timings["Imsak"]
					}
					
					# Calculate Dhuha manually: Sunrise + 20 minutes (approx)
					try:
						sunrise_h, sunrise_m = map(int, timings["Sunrise"].split(" ")[0].split(":"))
						# Use provided date or current time as base
						base_date = for_date if for_date else datetime.datetime.now()
						sunrise_dt = base_date.replace(hour=sunrise_h, minute=sunrise_m, second=0)
						dhuha_dt = sunrise_dt + datetime.timedelta(minutes=20)
						mapped_times["Dhuha"] = dhuha_dt.strftime("%H:%M")
					except Exception:
						mapped_times["Dhuha"] = timings["Sunrise"] # Fallback

					# Extract Hijri Date
					try:
						hijri = data["data"]["date"]["hijri"]
						
						# Month Translation Map (Standard Indonesian)
						# Including variations with diacritics as reported by user (e.g. Shaʿbān)
						month_map = {
							"Muharram": "Muharram",
							"Safar": "Safar",
							"Rabi' al-awwal": "Rabiul Awal",
							"Rabīʿ al-awwal": "Rabiul Awal",
							"Rabi' al-thani": "Rabiul Akhir",
							"Rabīʿ al-thānī": "Rabiul Akhir",
							"Jumada al-ula": "Jumadil Awal",
							"Jumādā al-ūlā": "Jumadil Awal",
							"Jumada al-akhirah": "Jumadil Akhir",
							"Jumādā al-ākhirah": "Jumadil Akhir",
							"Rajab": "Rajab",
							"Sha'ban": "Sya'ban",
							"Shaʿbān": "Sya'ban",
							"Ramadhan": "Ramadhan",
							"Ramadan": "Ramadhan",
							"Ramaḍān": "Ramadhan",
							"Shawwal": "Syawal",
							"Shawwāl": "Syawal",
							"Dhu al-Qi'dah": "Dzulqa'dah",
							"Dhū al-Qaʿdah": "Dzulqa'dah",
							"Dhu al-Hijjah": "Dzulhijjah",
							"Dhū al-Ḥijjah": "Dzulhijjah"
						}
						
						month_en = hijri['month']['en']
						
						# Standardize on Indonesian source string for gettext
						month_name = month_map.get(month_en, month_en)
						
						# --- Client-Side Adjustment Logic ---
						try:
							adj_int = int(adjustment)
							if adj_int != 0:
								day_val = int(hijri['day'])
								month_val = int(hijri['month']['number'])
								year_val = int(hijri['year'])
								max_days = int(hijri['month']['days']) # API returns length of current month
								
								day_val += adj_int
								
								# Forward Wrap
								if day_val > max_days:
									day_val -= max_days
									month_val += 1
									if month_val > 12:
										month_val = 1
										year_val += 1
										
								# Backward Wrap
								elif day_val < 1:
									# For backward wrap, we don't know the exact length of previous month.
									# But usually user does -1 to go from "1 Ramadan" to "30 Sya'ban".
									# So assuming 30 for the previous month is the safest "correction" assumption.
									day_val = 30 + day_val # e.g. 0 -> 30, -1 -> 29
									month_val -= 1
									if month_val < 1:
										month_val = 12
										year_val -= 1
								
								# Update values for formatting
								hijri['day'] = str(day_val)
								hijri['year'] = str(year_val)
								
								# Resolve new month name
								# Map 1-12 to English keys in month_map
								month_list = [
									"Muharram", "Safar", "Rabi' al-awwal", "Rabi' al-thani",
									"Jumada al-ula", "Jumada al-akhirah", "Rajab", "Sha'ban",
									"Ramadhan", "Shawwal", "Dhu al-Qi'dah", "Dhu al-Hijjah"
								]
								# Adjust index (1-based to 0-based)
								if 1 <= month_val <= 12:
									new_month_en = month_list[month_val - 1]
									month_name = month_map.get(new_month_en, new_month_en)
									
						except Exception as e:
							logHandler.log.error(f"IslamicPedia: Date adjustment error: {e}")
							# Fallback to original values if math fails

						# Translators: Hijri date format. date, month, year.
						# Example: "10 Syawal 1445 Hijriah"
						fmt = _("{day} {month} {year} Hijriah")
						
						# "21 Sya'ban 1447 Hijriah"
						hijri_str = fmt.format(day=hijri['day'], month=month_name, year=hijri['year'])
					except Exception:
						hijri_str = ""

					date_readable = data["data"]["date"]["readable"]
					return (date_readable, mapped_times, hijri_str)
					
		except Exception as e:
			logHandler.log.error(f"IslamicPedia: Error get_prayer_times (Aladhan): {e}")
		return ("", {}, "")
	def search_mosques(self, lat, lon, radius=1000):
		# Overpass API (OpenStreetMap)
		OVERPASS_URL = "https://overpass-api.de/api/interpreter"
		
		# Query: Find nodes/ways with amenity=place_of_worship AND religion=muslim
		query = f"""
			[out:json][timeout:25];
			(
			  node["amenity"="place_of_worship"]["religion"="muslim"](around:{radius},{lat},{lon});
			  way["amenity"="place_of_worship"]["religion"="muslim"](around:{radius},{lat},{lon});
			);
			out center;
		"""
		
		try:
			data = urllib.parse.urlencode({'data': query}).encode('utf-8')
			req = urllib.request.Request(OVERPASS_URL, data=data)
			req.add_header('User-Agent', 'IslamicPedia-NVDA-Addon/1.0')
			
			with urllib.request.urlopen(req, timeout=25) as response:
				result = json.loads(response.read().decode())
				elements = result.get('elements', [])
				
				mosques = []
				for el in elements:
					tags = el.get('tags', {})
					name = tags.get('name', tags.get('name:id', tags.get('name:en', _("Masjid Tanpa Nama"))))
					
					# Coordinates
					if 'center' in el:
						m_lat = float(el['center']['lat'])
						m_lon = float(el['center']['lon'])
					else:
						m_lat = float(el.get('lat', 0.0))
						m_lon = float(el.get('lon', 0.0))
						
					mosques.append({
						'name': name,
						'lat': m_lat,
						'lon': m_lon
					})
				
				return mosques
		except urllib.error.HTTPError as e:
			if e.code in [502, 503, 504]:
				logHandler.log.warning(f"IslamicPedia: Overpass API busy/timeout: {e}")
			else:
				logHandler.log.error(f"IslamicPedia: Error searching mosques (Overpass HTTP): {e}")
		except Exception as e:
			logHandler.log.error(f"IslamicPedia: Error searching mosques (Overpass): {e}")
		return []
