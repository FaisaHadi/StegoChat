# StegoChat Planning

## Tujuan proyek

StegoChat adalah proyek UTS yang mengenkripsi pesan dan menyembunyikan payload terautentikasi yang dihasilkan ke dalam gambar RGB. Penerima yang memberikan `stego_key` yang sama dapat secara deterministik menemukan payload, memvalidasinya, dan mendekripsinya. Proyek ini mendemonstrasikan kriptografi terapan, steganografi gambar, penanganan kapasitas, pemeriksaan integritas, dan pengukuran kualitas gambar secara objektif.

## Ruang lingkup

### Dalam ruang lingkup

- Alur kerja Streamlit lokal untuk menyembunyikan dan mengekstrak pesan dalam gambar RGB.
- PBKDF2-HMAC-SHA256 dengan 100.000 iterasi untuk menurunkan kunci AES-256 32 byte dari `stego_key` dan salt payload acak.
- Enkripsi dan autentikasi AES-256-GCM.
- Format payload V1, pemilihan posisi deterministik dua tahap, dan penyisipan LSB 1-bit pada kanal RGB sebagaimana didefinisikan dalam [System Design V1](system-design-v1.md).
- Validasi kapasitas sebelum memodifikasi gambar.
- Validasi ekstraksi, penanganan kegagalan yang jelas, dan pelaporan MSE/PSNR.
- Pengujian unit dan pengujian integrasi otomatis, dokumentasi, dan bukti demonstrasi.

### Di luar ruang lingkup

- Chat melalui jaringan, akun, autentikasi pengguna, basis data, penyimpanan cloud, atau layanan pengiriman pesan.
- Menyimpan, memulihkan, mengirimkan, atau mencatat nilai `stego_key`.
- Algoritma kriptografi kustom, mode enkripsi alternatif, atau skema derivasi kunci alternatif.
- Menyembunyikan data dalam audio, video, dokumen, gambar indexed-color, atau channel non-RGB.
- Kompresi, forward error correction, fragmentasi payload, klaim ketahanan terhadap steganalisis, atau jaminan covert-channel.
- Klien mobile, kolaborasi multi-pengguna, riwayat chat persisten, dan deployment produksi.

## Lightweight Scrum: rencana satu minggu

Tim beranggotakan tiga orang mengadakan stand-up harian singkat yang mencakup pekerjaan yang telah selesai, pekerjaan berikutnya, dan hambatan yang ada. Pekerjaan dipantau pada papan tugas yang terlihat, ditinjau dalam inkremen kecil, dan disesuaikan berdasarkan umpan balik pengujian.

| Hari | Fokus | Hasil yang diharapkan |
| --- | --- | --- |
| 1 | Konfirmasi persyaratan, dokumentasikan V1, dan siapkan struktur repository/pengujian | Protokol, peran, backlog, dan kriteria penerimaan yang telah disepakati |
| 2 | Implementasi dan pengujian kriptografi serta batas payload | Pengujian derivasi kunci, enkripsi/dekripsi, dan format berhasil |
| 3 | Implementasi dan pengujian posisi, pemeriksaan kapasitas, dan operasi RGB LSB | Primitif embed/extract deterministik berhasil |
| 4 | Integrasi jalur hide/extract dan metrik gambar | Round trip end-to-end dan kasus kegagalan berhasil |
| 5 | Implementasi alur kerja Streamlit dan validasi input | Jalur demonstrasi lokal yang dapat digunakan |
| 6 | Regression test, review oleh rekan, pengukuran kualitas, dan pengambilan bukti | Laporan pengujian, screenshot, dan aset demo |
| 7 | Hari cadangan, review dokumentasi, latihan, dan pengemasan pengumpulan tugas | Hasil siap dikumpulkan dengan keterbatasan yang dinyatakan |

## Product backlog dan epic

| Prioritas | Epic | Item backlog |
| --- | --- | --- |
| 1 | Fondasi protokol | Catat keputusan V1, konstanta, model error, dan acceptance test |
| 2 | Kriptografi dan payload | PBKDF2, AES-GCM, konstruksi/parsing payload V1, kegagalan autentikasi |
| 3 | Steganografi gambar | Validasi RGB, kapasitas, posisi berbasis HMAC, header yang dicadangkan, operasi LSB |
| 4 | Kualitas dan verifikasi | MSE/PSNR, pemeriksaan input tidak valid, pemeriksaan kunci salah/manipulasi, bukti pengujian yang dapat diulang |
| 5 | Alur kerja pengguna | Layar hide/extract Streamlit, penanganan file, validasi, status/error, unduhan |
| 6 | Kesiapan pengumpulan tugas | README, dokumen desain, hasil pengujian, gambar/screenshot demo, materi presentasi |

## Pembagian tanggung jawab tiga anggota

| Anggota tim | Tanggung jawab utama | Tanggung jawab review |
| --- | --- | --- |
| Anggota 1 | Kriptografi dan payload: PBKDF2, AES-GCM, batas payload V1, pengujian kriptografi | Review posisi dan pengujian integrasi |
| Anggota 2 | Steganografi dan metrik: validasi RGB, kapasitas, posisi deterministik, LSB, MSE/PSNR, pengujian gambar | Review pengujian kriptografi dan payload |
| Anggota 3 | Integrasi Streamlit dan implementasi penyerahan: validasi input/output, error pengguna, dokumentasi, bukti demo | Review alur end-to-end dan release checklist |

Semua anggota menghadiri stand-up, meninjau perubahan, dan berbagi tanggung jawab untuk pengujian integrasi dan regression testing.

## Definition of Done

Sebuah item backlog dinyatakan selesai hanya jika:

- Mengikuti System Design V1 dan telah di-review oleh rekan.
- Pengujian otomatis yang terfokus berhasil untuk kasus valid, batas, dan kasus kegagalan yang relevan.
- Perilaku penanganan kesalahan bersifat disengaja dan tidak mengekspos `stego_key` atau konten yang telah didekripsi.
- Dokumentasi dan perilaku yang terlihat diperbarui jika diperlukan.
- Tidak menambahkan dependensi, secret, atau perubahan repository yang tidak disetujui.
- Aplikasi yang terintegrasi tetap dapat menyelesaikan round trip hide/extract yang valid jika berlaku.

## Risiko teknis dan proyek utama

| Risiko | Dampak | Mitigasi |
| --- | --- | --- |
| Kapasitas gambar terlalu kecil | Payload tidak dapat di-embed | Hitung kapasitas sebelum modifikasi dan uji batas yang tepat |
| Posisi PRNG berbeda saat ekstraksi | Header/body tidak dapat dipulihkan | Gunakan seed HMAC-SHA256 yang ditentukan, pengambilan sampel unik deterministik, dan test vector; jangan pernah menggunakan `hash()` Python |
| Posisi header/body tumpang tindih | Data tertimpa atau ekstraksi menjadi tidak konsisten | Cadangkan posisi header dan kecualikan dari pemilihan body |
| `stego_key` salah atau payload dimanipulasi | Output dekripsi yang menyesatkan atau hilangnya integritas | Validasi field header dan wajibkan autentikasi AES-GCM sebelum mengembalikan plaintext |
| Penggunaan ulang nonce AES-GCM | Merusak jaminan keamanan AES-GCM | Buat nonce acak baru per payload dan uji batas konstruksinya |
| Inkonsistensi format payload | Komponen tidak dapat berinteroperasi | Pertahankan satu definisi format V1 dan build/parse test |
| Konversi gambar lossy | Bit yang di-embed dapat rusak | Wajibkan jalur output yang lossless dan mempertahankan RGB, lalu uji |
| Tekanan jadwal satu minggu | Pengumpulan tugas tidak lengkap atau kurang terverifikasi | Serahkan vertical slice lebih awal dan pertahankan hari cadangan di akhir |

## Pengujian dan deliverables tugas

Bukti pengumpulan tugas harus mencakup source code yang disetujui, manifest dependensi yang ada, rencana ini, System Design V1, dan README. Bukti verifikasi harus mencakup:

- Pengujian unit untuk derivasi kunci, perilaku sukses/gagal AES-GCM, field payload, posisi header/body deterministik, pengecualian posisi yang dicadangkan, operasi RGB LSB, batas kapasitas, MSE, dan PSNR.
- Pengujian integrasi untuk round trip pesan dan kasus `stego_key` salah, gambar/payload yang dimanipulasi, magic tidak valid, panjang tidak valid, mode gambar yang tidak didukung, dan kapasitas tidak mencukupi.
- Bukti demonstrasi yang menampilkan gambar cover/stego, ekstraksi berhasil, percobaan kunci salah atau manipulasi yang gagal, serta hasil MSE/PSNR.
- Presentasi atau laporan singkat yang menjelaskan arsitektur V1, batas keamanan, keterbatasan ruang lingkup yang dinyatakan, hasil pengujian, dan kontribusi masing-masing anggota.

StegoChat adalah implementasi edukatif. Hasil pengumpulan tugas tidak boleh mengklaim bahwa penyisipan LSB tidak dapat terdeteksi atau cukup sebagai kerahasiaan tingkat produksi secara mandiri.
