from site_scons.site_tools.NVDATool.typings import AddonInfo, BrailleTables, SymbolDictionaries
from site_scons.site_tools.NVDATool.utils import _

addon_info = AddonInfo(
	addon_name="IslamicPedia",
	addon_summary=_("Islamic Pedia"),
	addon_description=_(
		"Solusi lengkap kebutuhan Tunanetra Muslim: Jadwal Sholat, Arah Kiblat, Kalender Hijriyah, dan masih banyak fitur canggih lainnya dalam satu addon NVDA yang aksesibel.\n"
		"Cara pakai: Tekan shortcut NVDA + SHIFT + I (masuk ke mode Islamic Pedia). Tekan B atau F1 untuk menampilkan bantuan dan daftar perintah penggunaan."
	),
	addon_version="1.1.0",
	addon_changelog=_(
		"- Menambahkan fitur Kalkulator Zakat untuk menghitung 5 jenis zakat: Penghasilan, Maal (Harta/Tabungan), Emas, Perak, dan Fitrah.\n"
		"- Menambahkan shortcut Z untuk membuka Kalkulator Zakat (NVDA+Shift+I lalu Z).\n"
		"- Menambahkan input dinamis pada dialog Kalkulator Zakat yang berubah sesuai jenis zakat yang dipilih dari dropdown.\n"
		"- Menambahkan auto-fetch harga emas Antam Indonesia dari harga-emas.org saat dialog zakat dibuka, dengan fallback ke harga emas internasional jika gagal.\n"
		"- Menambahkan tombol Salin Hasil pada dialog Kalkulator Zakat yang muncul otomatis setelah ada hasil perhitungan.\n"
		"- Menambahkan pengaturan volume notifikasi (slider 0-100%) dengan live preview saat tombol test ditekan.\n"
		"- Menambahkan pemilihan perangkat audio output untuk notifikasi dengan fallback otomatis ke perangkat default.\n"
		"- Menambahkan grup Pengaturan Global di bagian atas tab Notifikasi.\n"
		"- Mengoptimalkan metode pemutaran audio notifikasi dari winsound ke waveOutOpen (WinMM) untuk file WAV.\n"
		"- Mengoptimalkan pengelolaan fokus dialog menggunakan pola standar NVDA (prePopup/postPopup).\n"
		"- Memperbaiki dialog pengaturan yang tidak langsung mendapat fokus saat pertama kali dibuka setelah restart NVDA.\n"
		"- Memperbaiki tombol Batal pada dialog pengaturan yang sebelumnya tidak memiliki handler."
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
