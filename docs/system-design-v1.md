# StegoChat System Design V1

## Tujuan dan keputusan V1 yang telah ditetapkan

StegoChat menyembunyikan payload terenkripsi pada bit paling tidak signifikan dari gambar RGB. V1 menggunakan string rahasia yang disediakan pengguna secara independen, disebut `stego_key`, untuk pemilihan posisi secara deterministik. String ini tidak pernah disimpan di dalam payload.

Salt payload acak tidak digunakan untuk menurunkan `stego_key`. Sebaliknya, salt merupakan metadata payload publik yang hanya digunakan bersama `stego_key` untuk menurunkan kunci enkripsi AES-256-GCM. Hal ini menghindari ketergantungan ekstraksi yang melingkar: posisi header dapat diturunkan sebelum salt diketahui.

## Arsitektur keseluruhan

```text
Pengirim: pesan + stego_key + gambar cover RGB
  -> PBKDF2-HMAC-SHA256(stego_key, random salt, 100000) -> AES-256 key
  -> AES-256-GCM(random nonce) -> ciphertext + authentication tag
  -> V1 payload: fixed header + ciphertext + tag
  -> deterministic header/body positions from stego_key
  -> one-bit RGB LSB embedding -> RGB stego image

Penerima: gambar stego RGB + stego_key
  -> header positions from stego_key -> fixed 34-byte header
  -> validate and parse magic, length, salt, nonce
  -> body positions from stego_key + salt -> ciphertext + tag
  -> PBKDF2-HMAC-SHA256(stego_key, salt, 100000) -> AES-256 key
  -> AES-256-GCM authentication and decryption -> message or failure
```

Antarmuka Streamlit di masa mendatang hanya akan menjadi batas presentasi. Antarmuka tersebut mendelegasikan pekerjaan protokol ke modul-modul proyek dan tidak boleh mendefinisikan perilaku kriptografi, payload, atau pemilihan posisi.

## Lapisan LSB versus lapisan kriptografi

V1 memisahkan embedding/pemilihan posisi secara ketat dari kriptografi. Tidak ada lapisan yang boleh menjalankan tugas lapisan lainnya:

| Lapisan | Modul | Tanggung jawab | Pantangan |
| --- | --- | --- | --- |
| Lapisan LSB | `stego/lsb.py`, `stego/prng.py`, `stego/capacity.py`, `stego/payload.py` | Pemilihan posisi RGB deterministik, pemeriksaan kapasitas, embed/extract LSB 1-bit, dan build/parse payload V1 pada level byte | Menurunkan kunci, mendekripsi, mengautentikasi, atau menghasilkan plaintext |
| Lapisan kriptografi | `crypto/kdf.py`, `crypto/aes.py` | Derivasi kunci PBKDF2-HMAC-SHA256 dan enkripsi/dekripsi AES-256-GCM | Membaca atau menulis piksel gambar, atau memilih posisi |
| Orkestrasi | `stegochat/core.py` | Menggabungkan kedua lapisan secara end-to-end | Mengimplementasikan ulang salah satu lapisan |

Konsekuensi utama, dinyatakan secara eksplisit:

- `stego.lsb.extract_payload()` mengembalikan **raw V1 payload** (`header + body`) persis seperti yang di-embed. Ini adalah operasi LSB saja. Fungsi ini tidak mengurai payload, menurunkan kunci, mengautentikasi, atau mendekripsi, dan tidak pernah mengembalikan plaintext.
- Plaintext dihasilkan **hanya** oleh `stegochat.core.extract_plaintext()`, yang mengonsumsi raw payload tersebut, mengurainya, menurunkan kunci AES, dan mendekripsi dengan AES-GCM setelah autentikasi berhasil.

## Alur kriptografi

1. Pengguna menyediakan byte rahasia `stego_key` secara independen. Representasi byte-nya harus tetap stabil antara operasi embed dan extract.
2. Buat salt acak 16 byte yang baru.
3. Turunkan kunci AES 32 byte dengan `PBKDF2-HMAC-SHA256(stego_key, salt, 100000 iterations)`.
4. Buat nonce acak 12 byte yang baru.
5. Enkripsi pesan dengan AES-256-GCM, menghasilkan ciphertext dan authentication tag 16 byte.
6. Bangun payload V1 dan embed bit-nya ke dalam gambar cover RGB.

Saat ekstraksi, turunkan kunci AES hanya setelah salt berhasil dipulihkan dari header. AES-GCM harus mengautentikasi sebelum plaintext diterima. `stego_key` yang salah, ciphertext/tag yang diubah, atau data yang rusak harus mengakibatkan kegagalan ekstraksi/dekripsi tanpa mengembalikan plaintext.

Salt dan nonce adalah metadata publik yang dibawa dalam payload. Keduanya tidak menggantikan kebutuhan untuk melindungi `stego_key`. Nonce harus baru untuk setiap enkripsi yang dilakukan dengan kunci AES turunan yang sama.

## Format payload

Payload sejajar byte dan diurutkan persis sebagai berikut:

```text
Magic 2B | Length 4B | Salt 16B | Nonce 12B | Ciphertext N | Auth Tag 16B
```

| Field | Ukuran | Makna |
| --- | ---: | --- |
| Magic | 2 byte | Identifier V1 yang digunakan untuk menolak gambar tanpa payload StegoChat |
| Length | 4 byte | Panjang byte dari `Ciphertext + Auth Tag` saja |
| Salt | 16 byte | Salt PBKDF2 acak; metadata publik |
| Nonce | 12 byte | Nonce AES-GCM baru; metadata publik |
| Ciphertext | N byte | Byte pesan terenkripsi AES-GCM |
| Auth Tag | 16 byte | Authentication tag AES-GCM |

Header tetap berukuran `2 + 4 + 16 + 12 = 34` byte, atau 272 bit. Body berukuran tepat `Length` byte dan berisi ciphertext diikuti authentication tag 16 byte. Nilai `Length` yang valid karenanya minimal 16 byte. Nilai ini tidak mencakup Magic, Length, Salt, atau Nonce.

### Konstanta field payload V1

| Konstanta | Nilai | Catatan |
| --- | --- | --- |
| Magic | `b"SG"` | Byte identifier V1 literal |
| Panjang Magic | 2 byte | Tetap |
| Length | Unsigned integer 4 byte | Jumlah byte body |
| Encoding Length | Big-endian | Diserialisasi dengan `int.to_bytes(4, "big")` |
| Makna Length | `len(ciphertext) + 16` | Ciphertext ditambah auth tag saja |
| Salt | 16 byte | Salt PBKDF2 acak |
| Nonce | 12 byte | Nonce AES-GCM baru |
| Auth tag | 16 byte | 16 byte terakhir dari body |
| Total header tetap | 34 byte | `2 + 4 + 16 + 12` = 272 bit |

Konstanta-konstanta ini didefinisikan oleh `stego/payload.py` (`MAGIC`, `MAGIC_LENGTH`, `LENGTH_FIELD_LENGTH`, `SALT_LENGTH`, `NONCE_LENGTH`, `AUTH_TAG_LENGTH`, `HEADER_SIZE`) dan tidak boleh berbeda antara embed dan extract.

## Embedding LSB 1-bit RGB dan kapasitas

Hanya gambar RGB yang didukung. Setiap byte kanal R, G, dan B adalah satu lokasi yang dapat di-embed. Satu bit payload menggantikan bit paling tidak signifikan dari satu kanal yang dipilih; semua bit yang lebih tinggi tetap tidak berubah.

Untuk lebar `W` dan tinggi `H`:

```text
Available channel positions (bits) = W * H * 3
Header bits                        = 34 * 8 = 272
Body bits                          = Length * 8
Required bits                      = 272 + (Length * 8)
```

Embedding hanya diizinkan jika:

```text
272 + (Length * 8) <= W * H * 3
```

Panjang body maksimum adalah:

```text
floor((W * H * 3 - 272) / 8) bytes
```

Kapasitas diperiksa sebelum gambar output dihasilkan. Gambar yang terlalu kecil untuk menampung header 34 byte tidak memiliki kapasitas payload V1 yang valid.

## PRNG deterministik dua tahap

V1 menggunakan dua seed turunan HMAC-SHA256 untuk pemilihan posisi deterministik:

```text
Header seed = HMAC-SHA256(stego_key, b"STEGOCHAT-HEADER")
Body seed   = HMAC-SHA256(stego_key, b"STEGOCHAT-BODY" + salt)
```

Header seed hanya bergantung pada `stego_key`. Penerima karenanya dapat mereproduksi posisi header dan mengekstrak header tetap sebelum mengetahui salt payload. Setelah salt diurai, body seed secara deterministik menemukan body terenkripsi.

Invarian pemilihan posisi:

- Pemilihan header menghasilkan tepat 272 posisi kanal RGB yang unik.
- Posisi header dicadangkan untuk header.
- Pemilihan body menghasilkan tepat `Length * 8` posisi unik dan mengecualikan setiap posisi header.
- Embed dan extract menggunakan pengindeksan kanal RGB dan prosedur pengambilan sampel deterministik yang sama.
- `stego_key` tidak di-embed, disimpan, dicatat, atau dikembalikan dalam pesan error.

`hash()` bawaan Python tidak boleh digunakan untuk menyemai proses ini. Python mengacak nilai `hash()` antar proses interpreter, sehingga tidak dapat mereproduksi posisi secara andal lintas eksekusi. HMAC-SHA256 bersifat keyed dan deterministik untuk `stego_key` dan byte input yang sama, sehingga cocok untuk derivasi seed yang diperlukan.

## Alur embed

1. Validasi gambar cover sebagai RGB dan hitung posisi kanal RGB yang tersedia.
2. Dapatkan `stego_key`; jangan simpan.
3. Buat salt dan nonce, turunkan kunci AES dengan PBKDF2-HMAC-SHA256 pada 100.000 iterasi, lalu enkripsi dengan AES-256-GCM.
4. Bangun header 34 byte dari Magic, Length, Salt, dan Nonce. Bangun body dari ciphertext ditambah authentication tag.
5. Validasi `272 + (Length * 8)` terhadap kapasitas gambar. Hentikan sebelum modifikasi jika tidak muat.
6. Turunkan header seed dari `stego_key` dan pilih 272 posisi header yang unik.
7. Turunkan body seed dari `stego_key` dan salt. Pilih posisi body unik yang diperlukan sambil mengecualikan semua posisi header.
8. Embed satu bit header di setiap posisi header dan satu bit body di setiap posisi body, lalu simpan melalui jalur yang lossless dan mempertahankan RGB.
9. Hitung MSE dan PSNR antara gambar cover dan stego.

## Alur extract

1. Validasi gambar input sebagai RGB dan konfirmasi memiliki setidaknya 272 posisi kanal RGB.
2. Dapatkan `stego_key`; jangan simpan.
3. Turunkan posisi header dari `stego_key`, ekstrak header tetap 34 byte, lalu validasi Magic dan urai Length, Salt, dan Nonce.
4. Tolak header yang tidak valid, termasuk `Length` di bawah 16 byte atau yang tidak muat dalam kapasitas gambar.
5. Turunkan body seed dari `stego_key` dan salt yang telah diurai. Reproduksi posisi body sambil mengecualikan posisi header, lalu ekstrak `Length` byte.
6. Pisahkan body menjadi ciphertext dan authentication tag 16 byte terakhir.
7. Turunkan kunci AES menggunakan `PBKDF2-HMAC-SHA256(stego_key, salt, 100000 iterations)` dan dekripsi dengan nonce dan tag yang diekstrak.
8. Kembalikan plaintext hanya setelah autentikasi AES-GCM berhasil. Perlakukan `stego_key` yang salah dan modifikasi payload yang dilindungi sebagai kegagalan ekstraksi/dekripsi.

Langkah 1–6 termasuk dalam lapisan LSB dan payload serta hanya beroperasi pada byte payload mentah. Langkah 7–8 termasuk dalam lapisan kriptografi. Hasil plaintext end-to-end hanya dirakit oleh `stegochat.core.extract_plaintext()`; `stego.lsb.extract_payload()` berhenti setelah langkah 6 dan mengembalikan `header + body`.

## MSE dan PSNR

Untuk gambar cover RGB 8-bit `I` dan gambar stego `K` berukuran sama, dengan lebar `W`, tinggi `H`, dan `C = 3` kanal:

```text
MSE = (1 / (W * H * C)) * sum((I[x,y,c] - K[x,y,c])^2)
```

```text
PSNR = 10 * log10((255^2) / MSE) dB
```

Jika MSE bernilai nol, PSNR bernilai tak terhingga. Metrik ini mengukur perbedaan piksel; keduanya tidak membuktikan bahwa embedding LSB tidak dapat terdeteksi atau tahan terhadap steganalisis.

## Kasus error

| Kondisi | Hasil yang diperlukan |
| --- | --- |
| Gambar tidak didukung atau bukan RGB | Tolak sebelum embedding atau ekstraksi |
| Gambar tidak dapat menampung header | Tolak sebagai kapasitas tidak mencukupi atau carrier tidak valid |
| Payload melebihi kapasitas | Tolak sebelum menghasilkan gambar output |
| Posisi header atau body duplikat/tumpang tindih | Perlakukan sebagai kegagalan invarian; jangan tulis atau kembalikan data |
| Magic tidak valid | Tolak sebagai tidak ada payload StegoChat V1 yang valid atau `stego_key` salah |
| `Length < 16` atau body tidak muat | Tolak sebagai payload tidak valid |
| Bit yang di-embed terpotong atau rusak | Tolak tanpa plaintext parsial |
| Kegagalan autentikasi AES-GCM | Tolak dekripsi; jangan bedakan kunci salah dari manipulasi kepada pengguna |
| Output lossy akan mengubah piksel | Tolak atau wajibkan format yang lossless dan mempertahankan RGB |

## Kontrak fungsi

Pipeline inti `crypto/`, `stego/`, dan `stegochat/` mengimplementasikan kontrak-kontrak berikut. Metrik `analysis/` (MSE/PSNR) dan antarmuka Streamlit masih bersifat dokumentasi saja dan belum diimplementasikan.

### Lapisan LSB dan payload

| Fungsi | Kontrak |
| --- | --- |
| `derive_aes_key(stego_key_bytes, salt) -> aes_key_bytes` | Memerlukan salt 16 byte, menerapkan PBKDF2-HMAC-SHA256 selama 100.000 iterasi, dan mengembalikan tepat 32 byte. |
| `encrypt_gcm(plaintext_bytes, aes_key_bytes, nonce) -> (ciphertext, auth_tag)` | Memerlukan kunci 32 byte dan nonce 12 byte; mengembalikan ciphertext dan tag 16 byte. |
| `decrypt_gcm(ciphertext, auth_tag, aes_key_bytes, nonce) -> plaintext_bytes` | Memerlukan kunci 32 byte, nonce 12 byte, dan tag 16 byte; gagal autentikasi tanpa mengembalikan plaintext. |
| `build_header(length, salt, nonce) -> header_bytes` | Memvalidasi ukuran field dan membuat tepat 34 byte dalam urutan field V1. |
| `parse_header(header_bytes) -> (length, salt, nonce)` | Memerlukan 34 byte, memvalidasi Magic/Length, dan menolak input yang tidak valid. |
| `header_seed(stego_key_bytes) -> seed_bytes` | Mengembalikan `HMAC-SHA256(stego_key, b"STEGOCHAT-HEADER")`. |
| `body_seed(stego_key_bytes, salt) -> seed_bytes` | Mengembalikan `HMAC-SHA256(stego_key, b"STEGOCHAT-BODY" + salt)`. |
| `select_positions(seed, width, height, count, excluded_positions) -> positions` | Mengembalikan `count` posisi RGB `(x, y, channel)` yang valid dan unik secara deterministik serta mengecualikan semua posisi yang dicadangkan; gagal jika tidak dapat memuat. |
| `stego.lsb.embed_payload(cover_rgb, header, body, stego_key_bytes) -> stego_rgb` | Lapisan LSB saja. Memvalidasi RGB/kapasitas, mencadangkan posisi header, mengecualikannya dari pemilihan body, dan hanya mengubah LSB kanal yang dipilih. Menulis header dan body yang diberikan pemanggil dan tidak pernah menurunkan kunci atau mengenkripsi. |
| `stego.lsb.extract_payload(stego_rgb, stego_key_bytes) -> raw_payload_bytes` | Lapisan LSB saja. Mengekstrak dan mengembalikan **raw V1 payload** (`header + body`) persis seperti yang di-embed. Tidak melakukan penguraian, derivasi kunci, autentikasi, atau dekripsi, dan tidak pernah mengembalikan plaintext. |
| `capacity_bits(width, height) -> int` | Mengembalikan `width * height * 3` untuk gambar RGB yang valid. |
| `mse(original_rgb, stego_rgb) -> float` | Memerlukan gambar RGB berukuran sama dan mengembalikan mean squared error kanal. Belum diimplementasikan. |
| `psnr(mse_value) -> float` | Mengembalikan nilai tak terhingga untuk MSE nol; selain itu menerapkan formula PSNR 8-bit. Belum diimplementasikan. |

### Lapisan orkestrasi inti

Fungsi-fungsi ini adalah satu-satunya entry point V1 yang menangani plaintext. Keduanya menggabungkan lapisan LSB/payload dan lapisan kriptografi serta memiliki batas plaintext.

| Fungsi | Kontrak |
| --- | --- |
| `stegochat.core.embed_plaintext(cover_rgb, plaintext, stego_key_bytes) -> stego_rgb` | Orkestrasi. Memvalidasi dan mengenkode plaintext ke UTF-8, menurunkan kunci AES dengan PBKDF2-HMAC-SHA256, mengenkripsi dengan AES-256-GCM, membangun payload V1, dan mendelegasikan embedding ke `stego.lsb.embed_payload`. |
| `stegochat.core.extract_plaintext(stego_rgb, stego_key_bytes) -> str` | Orkestrasi. Memanggil `stego.lsb.extract_payload` untuk mendapatkan raw V1 payload, mengurainya, menurunkan kunci AES, dan mengembalikan plaintext UTF-8 hanya setelah autentikasi dan dekripsi AES-GCM berhasil. Ini adalah satu-satunya jalur V1 yang menghasilkan plaintext. |

Pembagian tanggung jawab: lapisan LSB tidak pernah memegang kunci AES, dan lapisan kriptografi tidak pernah menyentuh piksel. Hanya `stegochat.core` yang menggabungkan keduanya, itulah mengapa `stego.lsb.extract_payload()` mengembalikan `header + body` dan bukan plaintext.

## Tanggung jawab modul repository

Repository sudah menyediakan scaffolding paket tingkat atas. Peta tanggung jawab berikut memandu implementasi selanjutnya tanpa menambahkan kode pada tahap ini.

| Path yang direncanakan | Tanggung jawab |
| --- | --- |
| `crypto/` | Derivasi kunci PBKDF2-HMAC-SHA256, enkripsi/dekripsi AES-256-GCM, dan batas kegagalan autentikasi |
| `stego/` | Penanganan payload V1, derivasi seed HMAC, posisi deterministik, validasi RGB, pemeriksaan kapasitas, dan orkestrasi embed/extract LSB |
| `analysis/` | MSE, PSNR, dan pelaporan kualitas non-protokol lainnya |
| `tests/` | Pengujian unit, batas, dan integrasi untuk semua kontrak V1 tanpa menyimpan rahasia nyata |
| `data/` | Aset sampel non-rahasia yang digunakan oleh pengujian/demonstrasi, tunduk pada tinjauan sumber/lisensi |
| `results/` | Artefak lokal yang dihasilkan seperti laporan atau gambar; dikecualikan dari Git oleh kebijakan ignore yang ada |
| `app.py` (masa mendatang) | Presentasi Streamlit dan alur kerja file/input; mendelegasikan ke `crypto/`, `stego/`, dan `analysis/` |

Tidak ada komponen yang boleh menyerialisasi `stego_key` ke dalam payload, log, pengujian, konfigurasi, atau hasil yang dihasilkan.
