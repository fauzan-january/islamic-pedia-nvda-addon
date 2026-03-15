## Changelog - Versi 1.1.0

- Menambahkan fitur Kalkulator Zakat untuk menghitung 5 jenis zakat: Penghasilan, Maal (Harta/Tabungan), Emas, Perak, dan Fitrah.
- Menambahkan shortcut Z untuk membuka Kalkulator Zakat (NVDA+Shift+I lalu Z).
- Menambahkan input dinamis pada dialog Kalkulator Zakat yang berubah sesuai jenis zakat yang dipilih dari dropdown.
- Menambahkan auto-fetch harga emas Antam Indonesia dari harga-emas.org saat dialog zakat dibuka, dengan fallback ke harga emas internasional jika gagal.
- Menambahkan tombol Salin Hasil pada dialog Kalkulator Zakat yang muncul otomatis setelah ada hasil perhitungan.
- Menambahkan pengaturan volume notifikasi (slider 0-100%) dengan live preview saat tombol test ditekan.
- Menambahkan pemilihan perangkat audio output untuk notifikasi dengan fallback otomatis ke perangkat default.
- Menambahkan grup Pengaturan Global di bagian atas tab Notifikasi.
- Mengoptimalkan metode pemutaran audio notifikasi dari winsound ke waveOutOpen (WinMM) untuk file WAV.
- Mengoptimalkan pengelolaan fokus dialog menggunakan pola standar NVDA (prePopup/postPopup).
- Memperbaiki dialog pengaturan yang tidak langsung mendapat fokus saat pertama kali dibuka setelah restart NVDA.
- Memperbaiki tombol Batal pada dialog pengaturan yang sebelumnya tidak memiliki handler.

## Changelog - Versi 1.0.0

- Rilis perdana Islamic Pedia NVDA Addon.
- Jadwal Sholat lima Waktu beserta Waktu Tambahan (Imsak, Terbit, dan Dhuha).
- Notifikasi Waktu Sholat dan Waktu Tambahan, Dilengkapi Pra-pengingat serta Audio yang Dapat Disesuaikan.
- Informasi Arah Kiblat Berdasarkan Lokasi Pengguna (Ditampilkan dalam Derajat dan Arah Mata Angin).
- Pencarian Masjid Terdekat (Radius 3km).
- Kalender Hijriyah dengan Sistem Pergantian Hari pada Waktu Maghrib sesuai Ketentuan Syariat Islam.
- Ensiklopedia Islami (Wikipedia).
- Penyesuaian Tanggal Hijriyah Manual (+/- 2 hari) jika ada perbedaan rukyat.
- Pilihan Metode Perhitungan Sholat (Kemenag RI, MWL, dll).
- Pilihan Mazhab Ashar (Syafi'i/Hanafi).
- Dukungan penuh Bahasa Indonesia.
