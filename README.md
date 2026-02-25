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

## Akun Default

| Username | Password | Role |
|----------|----------|------|
| admin | admin123 | Admin |
| staff01 | staff123 | Staff |
| manager01 | manager123 | Manager |
