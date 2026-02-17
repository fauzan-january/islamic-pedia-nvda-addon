import math

try:
	import addonHandler
	addonHandler.initTranslation()
except ImportError:
	import gettext
	def _(s): return s

def calculate_bearing(lat, lon):
	"""
	Calculates the bearing from a given location to the Kaaba.
	
	:param lat: Latitude of the location (float)
	:param lon: Longitude of the location (float)
	:return: Bearing in degrees (float)
	"""
	# Kaaba coordinates
	kaaba_lat = 21.422487
	kaaba_lon = 39.826206

	# Convert to radians
	lat_rad = math.radians(lat)
	lon_rad = math.radians(lon)
	kaaba_lat_rad = math.radians(kaaba_lat)
	kaaba_lon_rad = math.radians(kaaba_lon)

	# Calculate difference in longitude
	delta_lon = kaaba_lon_rad - lon_rad

	# Calculate bearing
	y = math.sin(delta_lon) * math.cos(kaaba_lat_rad)
	x = math.cos(lat_rad) * math.sin(kaaba_lat_rad) - \
		math.sin(lat_rad) * math.cos(kaaba_lat_rad) * math.cos(delta_lon)

	bearing_rad = math.atan2(y, x)
	bearing_deg = math.degrees(bearing_rad)

	# Normalize to 0-360
	bearing_deg = (bearing_deg + 360) % 360

	return bearing_deg

def get_cardinal_direction(degree):
	"""
	Returns the cardinal direction for a given degree.
	
	:param degree: Bearing in degrees (float)
	:return: Cardinal direction string (str)
	"""
	# Normalize degree
	degree = degree % 360
	
	if 337.5 <= degree or degree < 22.5:
		return _("Utara")
	elif 22.5 <= degree < 67.5:
		return _("Timur Laut")
	elif 67.5 <= degree < 112.5:
		return _("Timur")
	elif 112.5 <= degree < 157.5:
		return _("Tenggara")
	elif 157.5 <= degree < 202.5:
		return _("Selatan")
	elif 202.5 <= degree < 247.5:
		return _("Barat Daya")
	elif 247.5 <= degree < 292.5:
		return _("Barat")
	elif 292.5 <= degree < 337.5:
		return _("Barat Laut")
	return ""

def calculate_distance(lat1, lon1, lat2, lon2):
	"""
	Calculates the distance between two points on Earth using the Haversine formula.
	Returns distance in kilometers.
	"""
	R = 6371.0 # Radius of Earth in km
	
	dlat = math.radians(lat2 - lat1)
	dlon = math.radians(lon2 - lon1)
	
	a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
	c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
	
	distance = R * c
	return distance

def get_bearing_between(lat1, lon1, lat2, lon2):
	"""
	Calculates bearing from point 1 to point 2.
	"""
	# Convert to radians
	lat1 = math.radians(lat1)
	lon1 = math.radians(lon1)
	lat2 = math.radians(lat2)
	lon2 = math.radians(lon2)

	dLon = lon2 - lon1

	y = math.sin(dLon) * math.cos(lat2)
	x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dLon)
	brng = math.atan2(y, x)

	# Convert to degrees
	brng = math.degrees(brng)
	
	# Normalize to 0-360
	brng = (brng + 360) % 360
	return brng
