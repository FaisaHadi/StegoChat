# StegoChat

StegoChat adalah proyek UTS yang mengenkripsi pesan menggunakan AES-256-GCM dan menyembunyikan payload terautentikasi pada bit paling tidak signifikan (least significant bit) dari gambar RGB. Penerima yang mengetahui `stego_key` yang sama dapat secara deterministik menemukan, memvalidasi, dan mendekripsi pesan tersebut.

Protokol yang disepakati didokumentasikan di [System Design V1](docs/system-design-v1.md). Ruang lingkup pengerjaan dan perencanaan tim ada di [planning.md](docs/planning.md).

## Identitas Kelompok

**Kelompok 11**

| Nama | NIM |
| --- | --- |
| Faisal Hadi Saik | 247006111052 |
| Fadhila Hendani | 247006111053 |
| Irsyad Khoerul Umam | 247006111055 |

## Pipeline inti yang sudah diimplementasikan

Embedding (plaintext ke stego image):

```text
plaintext
  -> PBKDF2-HMAC-SHA256(stego_key, random salt, 100000) -> AES-256 key
  -> AES-256-GCM(random nonce) -> ciphertext + 16-byte auth tag
  -> V1 payload (34-byte header + body)
  -> PRNG: HMAC-SHA256-derived deterministic RGB positions
  -> RGB 1-bit LSB embedding
  -> stego image
```

Extraction (stego image kembali ke plaintext):

```text
stego image
  -> LSB extraction -> raw V1 payload (header + body)
  -> payload parsing (magic, length, salt, nonce, ciphertext, tag)
  -> PBKDF2-HMAC-SHA256(stego_key, salt, 100000) -> AES-256 key
  -> AES-256-GCM authenticate + decrypt
  -> plaintext
```

Pemisahan lapisan: `stego/lsb.py` hanya beroperasi pada byte payload mentah. `stego.lsb.extract_payload()` mengembalikan raw V1 payload (`header + body`) dan tidak pernah mendekripsi. Plaintext hanya dihasilkan oleh `stegochat/core.py`, setelah payload diurai dan autentikasi AES-GCM berhasil.

## Struktur repository

```text
crypto/               Derivasi kunci dan AES-256-GCM
  kdf.py                Derivasi kunci PBKDF2-HMAC-SHA256, pembuatan salt
  aes.py                Enkripsi/dekripsi AES-256-GCM, pembuatan nonce
stego/                Format payload, posisi PRNG, kapasitas, LSB
  payload.py            Build/parse V1 payload (magic, length, salt, nonce)
  prng.py               Pemilihan posisi RGB deterministik dengan HMAC-SHA256
  capacity.py           Perhitungan kapasitas channel RGB
  lsb.py                Embed/extract LSB 1-bit RGB pada level raw payload
stegochat/            Orkestrasi end-to-end
  core.py               embed_plaintext / extract_plaintext
analysis/             Metrik kualitas gambar dan alat steganalisis
  metrics.py            Perhitungan MSE dan PSNR
  histogram.py          Komputasi dan perbandingan histogram RGB
  bitplane.py           Ekstraksi dan visualisasi bit-plane LSB
  jpeg_fragility.py     Pengujian fragilitas rekompresi JPEG
  image_utils.py        Utilitas pemrosesan gambar bersama
laboratory.py         Runner eksperimen laboratorium dan ekspor XLSX
ui/                   Komponen antarmuka Streamlit
  messaging.py         Tab Embed & Send dan Extract & Read
  laboratory.py        Tab Laboratory & Security Testing
app.py                Shell, halaman awal, navigasi, dan gaya aplikasi
tests/                Unit test dan integration test untuk semua modul
data/                 Aset sampel untuk pengujian dan demonstrasi
docs/                 Dokumen desain sistem dan perencanaan
results/              Artefak lokal yang dihasilkan (diabaikan oleh Git)
```

## Pengaturan lingkungan

Buat dan aktifkan virtual environment dari root repository.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS atau Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

Instal dependensi dari manifest yang sudah ada:

```powershell
python -m pip install -r requirements.txt
```

`requirements.txt` adalah manifest dependensi bersama (streamlit, `cryptography`, Pillow, numpy, matplotlib, pandas, openpyxl, pytest). Pipeline inti hanya membutuhkan `cryptography`, Pillow, dan pytest.

## Menjalankan pengujian

Dari root repository:

```powershell
python -m pytest -q
```

## Contoh penggunaan pipeline inti

```python
from getpass import getpass
from PIL import Image

from stegochat.core import embed_plaintext, extract_plaintext

cover = Image.open("data/test_images/cover.png").convert("RGB")
stego_key = getpass("Masukkan stego-key: ").encode("utf-8")

stego = embed_plaintext(cover, "hello from StegoChat", stego_key)
stego.save("results/stego.png")  # format lossless wajib digunakan

recovered = extract_plaintext(
    Image.open("results/stego.png").convert("RGB"),
    stego_key,
)
assert recovered == "hello from StegoChat"
```

Kunci dimasukkan saat aplikasi dijalankan, bukan ditulis di kode atau disimpan dalam hasil ekspor. Runner bawaan membuat kunci acak sementara jika kunci tidak diberikan. Nilai dummy di unit test hanya merupakan data pengujian, bukan kredensial pengguna.

Proses ekstraksi memiliki dua lapisan validasi:

1. **Validasi format payload** (sebelum autentikasi kriptografi): Jika data LSB yang diekstrak tidak memiliki magic bytes V1 yang valid, `extract_plaintext` akan melempar `ValueError: invalid StegoChat V1 magic`. Ini terjadi sebelum autentikasi AES-GCM dan mengindikasikan `stego_key` yang salah (menghasilkan posisi LSB yang keliru), kerusakan akibat JPEG, atau data bukan StegoChat.

2. **Autentikasi AES-GCM** (setelah parsing payload): Jika ciphertext atau authentication tag rusak, atau `stego_key` salah, `decrypt_gcm()` akan melempar `cryptography.exceptions.InvalidTag`. Plaintext tidak akan pernah dikembalikan pada kedua kasus tersebut.

## Fitur yang sudah diimplementasikan

### Kriptografi Inti

- Enkripsi terautentikasi AES-256-GCM (`crypto/aes.py`).
- Derivasi kunci PBKDF2-HMAC-SHA256 dengan salt acak 16 byte pada 100.000 iterasi (`crypto/kdf.py`).
- Build dan parse V1 payload dengan header tetap 34 byte (`stego/payload.py`).
- Pemilihan posisi RGB deterministik HMAC-SHA256 dua tahap (`stego/prng.py`).
- Pemeriksaan kapasitas channel RGB (`stego/capacity.py`).
- Embedding dan ekstraksi LSB RGB 1-bit pada raw payload bytes (`stego/lsb.py`).
- Orkestrasi end-to-end `embed_plaintext` / `extract_plaintext` (`stegochat/core.py`).

### Metrik Kualitas Gambar

- Perhitungan Mean Squared Error (MSE) (`analysis/metrics.py`).
- Perhitungan Peak Signal-to-Noise Ratio (PSNR) (`analysis/metrics.py`).
- Komputasi dan perbandingan histogram RGB (`analysis/histogram.py`).
- Ekstraksi dan visualisasi bit-plane LSB (`analysis/bitplane.py`).

### Pengujian Keamanan

- Uji Chi-square Pairs-of-Values untuk mendeteksi indikasi steganografi (`analysis/chi_square.py`).
- Pengujian fragilitas rekompresi JPEG (`analysis/jpeg_fragility.py`).
- Runner eksperimen laboratorium otomatis (`laboratory.py`).
- Ekspor XLSX untuk hasil eksperimen (`laboratory.py`).

### Antarmuka Pengguna

- Aplikasi web Streamlit dengan 3 tab (`app.py`):
  - **Tab 1 - Embed & Send**: Upload cover image, masukkan pesan, embed dan unduh stego image.
  - **Tab 2 - Extract & Read**: Upload stego image, masukkan kunci, ekstrak dan dekripsi pesan.
  - **Tab 3 - Laboratory & Security Testing**: Analisis histogram, visualisasi bit-plane LSB, uji Chi-square, pengujian serangan JPEG, dan runner eksperimen.

### Pengujian Otomatis

- Unit test dan integration test untuk pipeline inti (`tests/`).
- Test eksperimen laboratorium (`tests/test_laboratory.py`).
- Total 111 test berhasil.

## Hasil Pengujian

Jalankan test suite:

```powershell
python -m pytest -q
```

Hasil saat ini: **111 tests passing**

## Artefak yang Dihasilkan

Jalankan runner eksperimen laboratorium untuk menghasilkan hasil:

```python
from laboratory import run_default_laboratory

results = run_default_laboratory()
print(f"Generated {len(results)} experiment results")
```

Ini menghasilkan `results/laboratory_results.xlsx` dengan data eksperimen untuk 5 gambar uji × 3 ukuran pesan = 15 kasus.

---

## Panduan Kolaborasi

Bagian ini ditujukan untuk anggota kelompok yang akan menggunakan repository ini dari laptop masing-masing.

### Tools yang diperlukan

Pastikan tools berikut sudah terinstal sebelum memulai:

- **Git** — untuk version control dan kolaborasi kode
- **Python** (versi yang kompatibel dengan dependency pada `requirements.txt`) — bahasa pemrograman utama proyek
- **Visual Studio Code** atau code editor lain — untuk menulis dan mengedit kode
- **Terminal / PowerShell** — untuk menjalankan perintah
- **Web browser** — untuk mengakses aplikasi Streamlit

Seluruh dependensi Python proyek tersedia di `requirements.txt` dan dapat diinstal sekaligus dengan satu perintah.

### Cara mendapatkan repository

Clone repository dari GitHub ke laptop masing-masing:

```bash
git clone https://github.com/FaisaHadi/StegoChat.git
cd StegoChat
```

### Setup Python Virtual Environment

Buat dan aktifkan virtual environment, lalu instal semua dependensi:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Kemudian upgrade pip dan instal dependensi:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Menjalankan aplikasi

Jalankan aplikasi web Streamlit dengan perintah berikut:

```powershell
streamlit run app.py
```

Aplikasi akan terbuka di browser secara otomatis. Terdapat tiga fitur utama:

- **Embed & Send** — upload gambar cover, masukkan pesan dan kunci, lalu unduh stego image yang sudah disisipi pesan terenkripsi.
- **Extract & Read** — upload stego image dan masukkan kunci yang sama untuk mengekstrak dan mendekripsi pesan.
- **Laboratory & Security Testing** — analisis histogram RGB, visualisasi bit-plane LSB, uji Chi-square, pengujian serangan JPEG, dan runner eksperimen otomatis.

### Menjalankan pengujian

Jalankan seluruh test suite dengan perintah:

```powershell
python -m pytest -q
```

Anggota kelompok **wajib menjalankan test sebelum dan sesudah melakukan perubahan kode** untuk memastikan tidak ada fungsionalitas yang rusak akibat perubahan yang dilakukan.

### Struktur repository

Berikut penjelasan singkat folder-folder utama dalam repository:

- `crypto/` — modul kriptografi: derivasi kunci (PBKDF2) dan enkripsi/dekripsi AES-256-GCM.
- `stego/` — modul steganografi: format payload V1, pemilihan posisi PRNG, perhitungan kapasitas, dan embedding/ekstraksi LSB.
- `stegochat/` — orkestrasi end-to-end yang menghubungkan kriptografi dan steganografi melalui `core.py`.
- `analysis/` — alat analisis: metrik kualitas gambar (MSE, PSNR), histogram RGB, visualisasi bit-plane, uji Chi-square, dan pengujian fragilitas JPEG.
- `tests/` — unit test dan integration test untuk semua modul.
- `data/` — aset sampel (gambar dan data uji) untuk keperluan pengujian dan demonstrasi.

### Workflow Git untuk anggota kelompok

Gunakan alur kerja berikut saat mengerjakan fitur atau perbaikan:

```text
main
  ↓
buat branch fitur/perbaikan
  ↓
kerjakan perubahan
  ↓
jalankan pytest
  ↓
git add
  ↓
git commit
  ↓
git push
  ↓
Pull Request
  ↓
review
  ↓
merge ke main
```

Mulai dengan memastikan branch `main` lokal sudah terbaru, lalu buat branch baru:

```bash
git checkout main
git pull origin main
git checkout -b feature/nama-fitur
```

Setelah selesai mengerjakan perubahan, lakukan langkah berikut sebelum push:

```bash
git status
git diff
python -m pytest -q
git add .
git commit -m "feat: deskripsi perubahan"
git push -u origin feature/nama-fitur
```

Setelah push, buat Pull Request di GitHub dan minta anggota lain untuk melakukan review sebelum di-merge ke `main`.

**Hal yang harus dihindari:**

- Jangan langsung melakukan perubahan besar di branch `main`.
- Jangan menggunakan `git push --force` tanpa koordinasi dengan anggota lain.
- Jangan menggunakan `git reset --hard` atau `git clean -fd` tanpa koordinasi, karena dapat menghapus perubahan yang belum di-commit.

### Aturan commit

Gunakan format commit yang deskriptif agar riwayat perubahan mudah dipahami oleh seluruh anggota:

```text
feat: add laboratory result download
fix: correct payload capacity calculation
test: add payload extraction tests
docs: update installation instructions
```

Setiap pesan commit harus menggambarkan dengan jelas perubahan apa yang dilakukan. Hindari pesan commit yang tidak informatif seperti `update`, `fix bug`, atau `changes`.

### Capaian proyek saat ini

Berikut adalah capaian yang sudah benar-benar ada dan berfungsi di repository:

**Fitur Aplikasi**
- Aplikasi web Streamlit dengan 3 tab: Embed & Send, Extract & Read, dan Laboratory & Security Testing.

**Komponen Kriptografi**
- Enkripsi dan dekripsi terautentikasi AES-256-GCM.
- Derivasi kunci PBKDF2-HMAC-SHA256 dengan salt acak 16 byte pada 100.000 iterasi.
- Build dan parse V1 payload dengan header tetap 34 byte.

**Komponen Steganografi**
- Pemilihan posisi RGB deterministik dua tahap berbasis HMAC-SHA256.
- Pemeriksaan kapasitas channel RGB.
- Embedding dan ekstraksi LSB 1-bit pada raw payload bytes.
- Orkestrasi end-to-end embed/extract plaintext.

**Laboratory & Security Testing**
- Perhitungan MSE dan PSNR.
- Komputasi dan perbandingan histogram RGB.
- Ekstraksi dan visualisasi bit-plane LSB.
- Uji Chi-square Pairs-of-Values untuk mendeteksi indikasi steganografi.
- Pengujian fragilitas rekompresi JPEG.
- Runner eksperimen otomatis dengan ekspor ke XLSX.

**Automated Testing**
- 111 test berhasil dijalankan.

## Fitur yang direncanakan (belum ada di kode saat ini)

Fitur-fitur ini dijelaskan dalam desain sistem tetapi belum ada dalam implementasi saat ini:

- Teknik steganalisis tambahan di luar Chi-square Pairs-of-Values.
- Metrik kualitas gambar lanjutan di luar MSE/PSNR.
- Metrik kemiripan perseptual (SSIM, dll.).
