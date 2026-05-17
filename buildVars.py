from site_scons.site_tools.NVDATool.typings import AddonInfo, BrailleTables, SymbolDictionaries
from site_scons.site_tools.NVDATool.utils import _

addon_info = AddonInfo(
	addon_name="IslamicPedia",
	addon_summary=_("Islamic Pedia"),
	addon_description=_(
		"Solusi lengkap kebutuhan Tunanetra Muslim: Jadwal Sholat, Arah Kiblat, Kalender Hijriyah, dan masih banyak fitur canggih lainnya dalam satu addon NVDA yang aksesibel.\n"
		"Cara pakai: Tekan shortcut NVDA + SHIFT + I (masuk ke mode Islamic Pedia). Tekan B atau F1 untuk mengakses Bantuan dan Dokumentasi Lengkap."
	),
	addon_version="1.2.0",
	addon_changelog=_(
		"- Meningkatkan dukungan dan kompatibilitas untuk NVDA versi 2026.1.\n"
		"- Memperbaiki sejumlah bug dan potensi error yang terdeteksi.\n"
		"- Memperbaiki masalah fokus pada dialog \"Masjid Terdekat\" agar langsung dapat dibaca oleh pembaca layar saat pertama kali dibuka.\n"
		"- Menambahkan menu interaktif pada perintah Bantuan (F1 atau B) untuk memilih antara membuka \"Daftar Perintah\" atau \"Dokumentasi Lengkap\".\n"
		"- Memperbarui antarmuka pratinjau audio di pengaturan notifikasi; tombol \"Berhenti\" kini akan otomatis kembali menjadi \"Tes\" saat pemutaran audio selesai.\n"
		"- Menambahkan tombol \"Muat Ulang\" untuk memutakhirkan harga emas secara manual pada kalkulator zakat.\n"
		"- Meningkatkan indikator proses pengunduhan audio pratinjau agar lebih intuitif.\n"
		"- Mengoptimalkan pemuatan Tab Notifikasi agar langsung dimuat saat dialog pengaturan dibuka.\n"
		"- Menyeragamkan daftar metode kalkulasi waktu sholat menggunakan bahasa Indonesia sepenuhnya.\n"
		"- Memperbaiki integrasi menu pengaturan; kini pengaturan Islamic Pedia dapat diakses langsung melalui menu Pengaturan bawaan NVDA, tidak lagi hanya bergantung pada lapisan perintah.\n"
		"- Menambahkan dan menyesuaikan beberapa varian suara baru untuk notifikasi audio."
	),
	addon_author="Fauzan January <surel@fauzanaja.com>",
	addon_url="https://fauzanaja.com/nvda-addon/",
	addon_sourceURL="https://github.com/fauzan-january/islamic-pedia/",
	addon_docFileName="readme.html",
	addon_minimumNVDAVersion="2024.1",
	addon_lastTestedNVDAVersion="2026.1",
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
