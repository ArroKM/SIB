# Surat Izin Keluar Masuk Barang

Sistem informasi pengelolaan surat izin keluar dan masuk barang untuk **PT PLN Indonesia Power** — UBP Jawa Tengah 2 Adipala.

## Fitur

- **Login & Register** — autentikasi dengan role (admin, staff, manager)
- **Surat Izin Keluar Barang** — buat, edit, lihat, hapus surat izin keluar
- **Surat Izin Masuk Barang** — buat, edit, lihat, hapus surat izin masuk
- **Dashboard Analitik** — statistik bulanan, per divisi, chart interaktif (Chart.js)
- **Lampiran Foto** — upload foto barang langsung di form surat
- **Status Persetujuan** — alur pending → disetujui / ditolak dengan catatan
- **Export PDF** — export surat per lembar (modern, tanda tangan rapi) via WeasyPrint
- **Export PDF Laporan** — rekap seluruh surat dalam format PDF landscape
- **Export Excel** — rekap seluruh surat dalam format XLSX dengan styling
- **Kelola User** — admin dapat mengubah role dan menonaktifkan user
- **Log Aktivitas** — audit trail seluruh aksi di sistem
- **Desain Modern** — Tailwind CSS, sidebar, responsif

## Teknologi

| Komponen | Teknologi |
|----------|-----------|
| Backend | Python / Flask |
| Database | MySQL (PyMySQL) |
| Frontend | Tailwind CSS (CDN), Chart.js |
| Auth | Flask-Login, bcrypt |
| PDF | WeasyPrint |
| Excel | openpyxl |

## Instalasi

```bash
# 1. Clone repository
git clone https://github.com/ArroKM/SIB.git
cd SIB

# 2. Install dependencies
pip install -r requirements.txt

# 3. Konfigurasi database — salin .env.example lalu sesuaikan
cp .env.example .env
# Edit .env sesuai konfigurasi MySQL Anda

# 4. Jalankan aplikasi (database & tabel dibuat otomatis)
python app.py
```

> **Catatan:** Aplikasi menggunakan **auto-migration** — database, tabel, dan
> kolom baru akan dibuat/ditambahkan secara otomatis saat startup. Tidak perlu
> menjalankan `database.sql` secara manual. File `database.sql` tetap disertakan
> sebagai referensi schema.

Aplikasi akan berjalan di `http://localhost:8000`.

## Akun Default

| Username | Password | Role |
|----------|----------|------|
| admin | admin123 | Admin |
| staff01 | staff123 | Staff |
| manager01 | manager123 | Manager |

## Struktur File

```
├── app.py              # Aplikasi Flask utama
├── config.py           # Konfigurasi aplikasi & database
├── db.py               # Koneksi MySQL & inisialisasi tabel
├── database.sql        # SQL schema untuk setup manual
├── requirements.txt    # Dependensi Python
├── static/
│   ├── uploads/        # File foto yang di-upload
│   ├── pdfs/           # File PDF yang di-generate
│   └── style.css       # Custom CSS (legacy)
└── templates/
    ├── base.html           # Layout utama (sidebar, header)
    ├── login.html          # Halaman login
    ├── register.html       # Halaman registrasi
    ├── dashboard.html      # Dashboard analitik
    ├── surat_list.html     # Daftar surat + filter
    ├── add_surat.html      # Form buat surat baru
    ├── edit_surat.html     # Form edit surat
    ├── view_surat.html     # Detail surat + status
    ├── pdf_template.html   # Template PDF surat
    ├── report_pdf.html     # Template PDF laporan
    ├── users.html          # Manajemen user (admin)
    ├── activity.html       # Log aktivitas (admin)
    └── error.html          # Halaman error
```
