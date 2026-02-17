import urllib.request
import urllib.parse
import json
import logHandler
import re

try:
	import addonHandler
	addonHandler.initTranslation()
except ImportError:
	import gettext
	def _(s): return s

class WikiAPI:
	def __init__(self, lang="id"):
		self.base_url = f"https://{lang}.wikipedia.org/w/api.php"
		self.headers = {
			'User-Agent': 'IslamicPedia-NVDA-Addon/1.0 (https://github.com/fauzan-january/IslamicPedia)'
		}

	def search(self, query, limit=5):
		"""
		Searches Wikipedia using 'list=search' (srsearch) to filter for Islamic context.
		Appends ' Islam' to the query to prioritize Islamic topics.
		"""
		try:
			# Smart Filter: Append "Islam" if not already present logic
			# to clear ambiguity (e.g. "Wudhu" -> "Wudhu Islam")
			if "islam" not in query.lower():
				search_query = f"{query} Islam"
			else:
				search_query = query

			params = {
				"action": "query",
				"list": "search",
				"srsearch": search_query,
				"srlimit": limit,
				"format": "json"
			}
			
			url = f"{self.base_url}?{urllib.parse.urlencode(params)}"
			request = urllib.request.Request(url, headers=self.headers)
			
			with urllib.request.urlopen(request, timeout=10) as response:
				data = json.loads(response.read().decode())
				# Format: data['query']['search'] -> list of dicts [{'title': ...}, ...]
				search_results = data.get("query", {}).get("search", [])
				
				# Return list of titles
				return [item["title"] for item in search_results]

		except Exception as e:
			logHandler.log.error(f"IslamicPedia: Wiki search error: {e}")
			return []

	def get_article(self, title):
		"""
		Fetches the FULL article content of a page.
		Strictly validates content against Islamic keywords using regex.
		"""
		# List of keywords to validate if the content is Islamic
		ISLAMIC_KEYWORDS = (
			"islam", "muslim", "allah", "nabi", "rasul", "prophet", "messenger",
			"quran", "alquran", "hadis", "hadith", "syariah", "sharia", "fiqih", "fiqh",
			"iman", "faith", "tauhid", "tawhid", "sunnah", "ulama", "scholar",
			"pesantren", "madrasa", "masjid", "mosque", "hijriyah", "hijri",
			"zakat", "charity", "puasa", "fasting", "ramadan", "ramadhan",
			"haji", "hajj", "umrah", "dakwah", "da'wah", "khilafah", "caliphate",
			"sahabat", "companion", "tabiin", "sufi", "tasawuf", "sufism",
			"akidah", "aqidah", "akhlak", "ethics", "ibadah", "worship", "muamalah",
			"sejarah islam", "islamic history", "kebudayaan islam", "islamic culture",
			"wali", "saint", "kiai", "sheikh", "ustad", "ustadz"
		)

		try:
			params = {
				"action": "query",
				"format": "json",
				"prop": "extracts|categories",
				"cllimit": "max",
				"titles": title,
				"explaintext": 1,
				"redirects": 1
			}
			
			url = f"{self.base_url}?{urllib.parse.urlencode(params)}"
			request = urllib.request.Request(url, headers=self.headers)
			
			with urllib.request.urlopen(request, timeout=10) as response:
				data = json.loads(response.read().decode())
				pages = data.get("query", {}).get("pages", {})
				
				for page_id, page_data in pages.items():
					if page_id == "-1":
						return None # Not found
					
					title_text = page_data.get("title", title)
					extract_text = page_data.get("extract", "")
					categories = page_data.get("categories", [])
					
					# Strict Validation: Check Title OR Categories
					# We STOP checking the 'extract' (content) because it causes false positives
					# (e.g. "Mobil" article passing because it mentions "Bank Syariah")
					
					is_islamic = False
					
					# 1. Check Title
					title_lower = title_text.lower()
					for k in ISLAMIC_KEYWORDS:
						if re.search(r'\b' + re.escape(k) + r'\b', title_lower):
							is_islamic = True
							break
					
					# 2. Check Categories (if title didn't match)
					if not is_islamic:
						for cat in categories:
							# Format: "Kategori:Sejarah Islam"
							cat_title = cat.get("title", "").lower()
							for k in ISLAMIC_KEYWORDS:
								if re.search(r'\b' + re.escape(k) + r'\b', cat_title):
									is_islamic = True
									break
							if is_islamic:
								break
					
					if not is_islamic:
						logHandler.log.info(f"IslamicPedia: Filtered out non-Islamic topic (Category mismatch): {title}")
						return None # Filtered out as non-Islamic

					return {
						"title": title_text,
						"extract": extract_text,
						"url": f"https://id.wikipedia.org/wiki/{urllib.parse.quote(title_text.replace(' ', '_'))}"
					}
				return None
		except Exception as e:
			logHandler.log.error(f"IslamicPedia: Wiki summary error: {e}")
			return None
