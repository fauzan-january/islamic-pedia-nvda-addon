from site_scons.site_tools.NVDATool.typings import AddonInfo, BrailleTables, SymbolDictionaries
from site_scons.site_tools.NVDATool.utils import _

addon_info = AddonInfo(
	addon_name="IslamicPedia",
	addon_summary=_("Islamic Pedia"),
	addon_description=_(
		"Solusi lengkap kebutuhan Tunanetra Muslim: Jadwal Sholat, Arah Kiblat, Kalender Hijriyah, dan masih banyak fitur canggih lainnya dalam satu addon NVDA yang aksesibel.\n"
		"Cara pakai: Tekan shortcut NVDA + SHIFT + I (masuk ke mode Islamic Pedia). Tekan B atau F1 untuk menampilkan bantuan dan daftar perintah penggunaan."
	),
	addon_version="1.0.0",
	addon_changelog=_(
		"- Rilis perdana Islamic Pedia NVDA Addon.\n"
		"- Jadwal Sholat lima Waktu beserta Waktu Tambahan (Imsak, Terbit, dan Dhuha).\n"
		"- Notifikasi Waktu Sholat dan Waktu Tambahan, Dilengkapi Pra-pengingat serta Audio yang Dapat Disesuaikan.\n"
		"- Informasi Arah Kiblat Berdasarkan Lokasi Pengguna (Ditampilkan dalam Derajat dan Arah Mata Angin).\n"
		"- Pencarian Masjid Terdekat (Radius 3km).\n"
		"- Kalender Hijriyah dengan Sistem Pergantian Hari pada Waktu Maghrib sesuai Ketentuan Syariat Islam.\n"
		"- Ensiklopedia Islami (Wikipedia).\n"
		"- Penyesuaian Tanggal Hijriyah Manual (+/- 2 hari) jika ada perbedaan rukyat.\n"
		"- Pilihan Metode Perhitungan Sholat (Kemenag RI, MWL, dll).\n"
		"- Pilihan Mazhab Ashar (Syafi'i/Hanafi).\n"
		"- Dukungan penuh Bahasa Indonesia."
	),
	addon_author="Fauzan January <surel@fauzanaja.com>",
	addon_url="https://fauzanaja.com/nvda-addon/",
	addon_sourceURL="https://github.com/fauzan-january/islamic-pedia/",
	addon_docFileName="readme.html",
	addon_minimumNVDAVersion="2024.1",
	addon_lastTestedNVDAVersion="2025.3",
	addon_updateChannel=None,
	addon_license="GPL-2.0",
	addon_licenseURL="https://www.gnu.org/licenses/gpl-2.0.html",
)

pythonSources: list[str] = [
	"addon/globalPlugins/IslamicPedia/*.py",
	"addon/installTasks.py",
]

i18nSources: list[str] = pythonSources + ["buildVars.py"]

excludedFiles: list[str] = ["tests"]

baseLanguage: str = "id"

markdownExtensions: list[str] = []

brailleTables: BrailleTables = {}

symbolDictionaries: SymbolDictionaries = {}
