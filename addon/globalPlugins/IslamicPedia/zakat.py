# -*- coding: utf-8 -*-
# Zakat Calculator Module for Islamic Pedia NVDA Addon
# Provides calculation functions for various types of zakat.

import urllib.request
import json
import logHandler

try:
	import addonHandler
	addonHandler.initTranslation()
except ImportError:
	def _(s): return s

# --- Constants ---
NISAB_GOLD_GRAM = 85       # Nisab emas: 85 gram
NISAB_SILVER_GRAM = 595    # Nisab perak: 595 gram
ZAKAT_RATE = 0.025         # Tarif zakat: 2.5%
FITRAH_KG_PER_PERSON = 2.5 # Zakat fitrah: 2.5 kg beras per jiwa

import re


def fetch_gold_price():
	"""Fetch current gold price per gram in IDR.
	
	Strategy (3-tier):
	1. Scrape harga emas Antam dari harga-emas.org (harga lokal Indonesia)
	2. Fallback: harga internasional (CoinGecko + kurs USD/IDR)
	3. Fallback terakhir: return None (pengguna input manual)
	
	Returns price as float (Rp per gram), or None if all methods fail.
	"""
	headers = {'User-Agent': 'IslamicPedia-NVDA-Addon/1.0'}

	# === Method 1: Scrape harga emas Antam dari harga-emas.org ===
	price = _fetch_from_harga_emas_org(headers)
	if price:
		return price

	# === Method 2: Harga internasional (USD) × kurs IDR ===
	price = _fetch_international_price(headers)
	if price:
		return price

	return None


def _fetch_from_harga_emas_org(headers):
	"""Scrape harga emas Antam 1 gram dari harga-emas.org."""
	try:
		url = "https://harga-emas.org/"
		req = urllib.request.Request(url, headers=headers)
		with urllib.request.urlopen(req, timeout=15) as response:
			html = response.read().decode('utf-8')
			
			import json
			# Cari dari JSON-LD Web Schema (Paling akurat & format numerik asli)
			json_ld_blocks = re.findall(r'<script type=[\'\"]application/ld\+json[\'\"]>(.*?)</script>', html, re.IGNORECASE | re.DOTALL)
			for block in json_ld_blocks:
				try:
					data = json.loads(block)
					if data.get('@type') == 'Product' and 'offers' in data:
						price_val = data['offers'].get('price')
						if price_val and 1_000_000 <= int(float(price_val)) <= 5_000_000:
							logHandler.log.info(
								f"IslamicPedia: Harga emas Indonesia (JSON-LD harga-emas.org): "
								f"Rp {int(float(price_val)):,}/gram"
							)
							return float(price_val)
				except Exception:
					pass

			# Fallback 1: Jika tidak ada JSON-LD, cari spesifik baris 1 gram Antam
			# Hanya mengambil angka format Rupiah setelah menyebut "Emas 1 Gram" / baris "1"
			# Menghindari terbacanya "Spot", tanggal, atau emas kelipatan besar.
			matches = re.search(r'Emas\s*1\s*Gram.*?(\d{1,3}(?:\.\d{3})+)', html, re.IGNORECASE | re.DOTALL)
			if not matches:
				matches = re.search(r'>\s*1\s*<[^>]{0,100}?>\s*(\d{1,3}(?:\.\d{3})+)', html, re.IGNORECASE | re.DOTALL)

			if matches:
				price_val = int(matches.group(1).replace('.', ''))
				if 1_000_000 <= price_val <= 5_000_000:
					logHandler.log.info(
						f"IslamicPedia: Harga emas Indonesia (Regex harga-emas.org): "
						f"Rp {price_val:,}/gram"
					)
					return float(price_val)
	except Exception as e:
		logHandler.log.warning(f"IslamicPedia: Failed to scrape harga-emas.org: {e}")
	return None


def _fetch_international_price(headers):
	"""Fallback: get gold price via international APIs (USD × IDR rate)."""
	# Step 1: Get USD to IDR exchange rate
	usd_to_idr = None
	try:
		url = "https://api.exchangerate-api.com/v4/latest/USD"
		req = urllib.request.Request(url, headers=headers)
		with urllib.request.urlopen(req, timeout=10) as response:
			data = json.loads(response.read().decode('utf-8'))
			usd_to_idr = data.get("rates", {}).get("IDR")
			if usd_to_idr:
				logHandler.log.info(f"IslamicPedia: USD/IDR rate: {usd_to_idr}")
	except Exception as e:
		logHandler.log.warning(f"IslamicPedia: Failed to get USD/IDR rate: {e}")

	if not usd_to_idr:
		return None

	# Step 2: Get gold price in USD from CoinGecko (Tether Gold = 1 troy oz)
	try:
		url = "https://api.coingecko.com/api/v3/simple/price?ids=tether-gold&vs_currencies=usd"
		req = urllib.request.Request(url, headers=headers)
		with urllib.request.urlopen(req, timeout=10) as response:
			data = json.loads(response.read().decode('utf-8'))
			if "tether-gold" in data and "usd" in data["tether-gold"]:
				gold_usd_per_ounce = float(data["tether-gold"]["usd"])
				# 1 troy ounce = 31.1035 grams
				price_per_gram_usd = gold_usd_per_ounce / 31.1035
				price_per_gram_idr = price_per_gram_usd * usd_to_idr
				logHandler.log.info(
					f"IslamicPedia: Gold price (international fallback): "
					f"Rp {price_per_gram_idr:,.0f}/gram"
				)
				return price_per_gram_idr
	except Exception as e:
		logHandler.log.warning(f"IslamicPedia: Failed to fetch gold price (coingecko): {e}")

	return None


def calc_zakat_penghasilan(monthly_income, gold_price_per_gram):
	"""Calculate Zakat Penghasilan (income zakat).
	
	Args:
		monthly_income: Monthly income in IDR
		gold_price_per_gram: Current gold price per gram in IDR
	
	Returns:
		dict with keys: wajib, nisab_value, yearly_income, zakat_monthly, zakat_yearly
	"""
	yearly_income = monthly_income * 12
	nisab_value = NISAB_GOLD_GRAM * gold_price_per_gram

	if yearly_income >= nisab_value:
		zakat_yearly = yearly_income * ZAKAT_RATE
		zakat_monthly = monthly_income * ZAKAT_RATE
		return {
			"wajib": True,
			"nisab_value": nisab_value,
			"yearly_income": yearly_income,
			"zakat_yearly": zakat_yearly,
			"zakat_monthly": zakat_monthly,
		}
	else:
		return {
			"wajib": False,
			"nisab_value": nisab_value,
			"yearly_income": yearly_income,
			"zakat_yearly": 0,
			"zakat_monthly": 0,
		}


def calc_zakat_maal(total_wealth, gold_price_per_gram):
	"""Calculate Zakat Maal (wealth zakat).
	
	Args:
		total_wealth: Total savings/wealth held for >= 1 year in IDR
		gold_price_per_gram: Current gold price per gram in IDR
	
	Returns:
		dict with keys: wajib, nisab_value, total_wealth, zakat
	"""
	nisab_value = NISAB_GOLD_GRAM * gold_price_per_gram

	if total_wealth >= nisab_value:
		zakat = total_wealth * ZAKAT_RATE
		return {
			"wajib": True,
			"nisab_value": nisab_value,
			"total_wealth": total_wealth,
			"zakat": zakat,
		}
	else:
		return {
			"wajib": False,
			"nisab_value": nisab_value,
			"total_wealth": total_wealth,
			"zakat": 0,
		}


def calc_zakat_gold(weight_gram, gold_price_per_gram):
	"""Calculate Zakat Emas (gold zakat).
	
	Args:
		weight_gram: Weight of gold owned in grams
		gold_price_per_gram: Current gold price per gram in IDR
	
	Returns:
		dict with keys: wajib, nisab_gram, weight, value, zakat_gram, zakat_value
	"""
	value = weight_gram * gold_price_per_gram

	if weight_gram >= NISAB_GOLD_GRAM:
		zakat_gram = weight_gram * ZAKAT_RATE
		zakat_value = value * ZAKAT_RATE
		return {
			"wajib": True,
			"nisab_gram": NISAB_GOLD_GRAM,
			"weight": weight_gram,
			"value": value,
			"zakat_gram": zakat_gram,
			"zakat_value": zakat_value,
		}
	else:
		return {
			"wajib": False,
			"nisab_gram": NISAB_GOLD_GRAM,
			"weight": weight_gram,
			"value": value,
			"zakat_gram": 0,
			"zakat_value": 0,
		}


def calc_zakat_silver(weight_gram, silver_price_per_gram):
	"""Calculate Zakat Perak (silver zakat).
	
	Args:
		weight_gram: Weight of silver owned in grams
		silver_price_per_gram: Current silver price per gram in IDR
	
	Returns:
		dict with keys: wajib, nisab_gram, weight, value, zakat_gram, zakat_value
	"""
	value = weight_gram * silver_price_per_gram

	if weight_gram >= NISAB_SILVER_GRAM:
		zakat_gram = weight_gram * ZAKAT_RATE
		zakat_value = value * ZAKAT_RATE
		return {
			"wajib": True,
			"nisab_gram": NISAB_SILVER_GRAM,
			"weight": weight_gram,
			"value": value,
			"zakat_gram": zakat_gram,
			"zakat_value": zakat_value,
		}
	else:
		return {
			"wajib": False,
			"nisab_gram": NISAB_SILVER_GRAM,
			"weight": weight_gram,
			"value": value,
			"zakat_gram": 0,
			"zakat_value": 0,
		}


def calc_zakat_fitrah(num_people, rice_price_per_kg):
	"""Calculate Zakat Fitrah.
	
	Args:
		num_people: Number of family members
		rice_price_per_kg: Price of rice per kg in IDR
	
	Returns:
		dict with keys: num_people, kg_per_person, total_kg, total_value
	"""
	total_kg = num_people * FITRAH_KG_PER_PERSON
	total_value = total_kg * rice_price_per_kg
	return {
		"num_people": num_people,
		"kg_per_person": FITRAH_KG_PER_PERSON,
		"total_kg": total_kg,
		"total_value": total_value,
	}


def format_rupiah(value):
	"""Format a number as Indonesian Rupiah string."""
	if value >= 0:
		return f"Rp {value:,.0f}".replace(",", ".")
	else:
		return f"-Rp {abs(value):,.0f}".replace(",", ".")
