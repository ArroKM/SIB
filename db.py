import re

import pymysql
import pymysql.cursors
from config import Config


def _safe_identifier(name):
    """Validate that *name* is a safe SQL identifier (letters, digits, underscore)."""
    if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', name):
        raise ValueError(f"Unsafe SQL identifier: {name!r}")
    return name

def get_db():
    """Get a MySQL database connection returning dict rows."""
    conn = pymysql.connect(
        host=Config.MYSQL_HOST,
        port=Config.MYSQL_PORT,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        database=Config.MYSQL_DB,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor,
    )
    return conn


def init_db():
    """Create database/tables, run auto-migrations, and seed initial data.

    This function is safe to call on every startup.  ``CREATE TABLE IF NOT
    EXISTS`` handles fresh installs, and ``_migrate_table`` adds any columns
    that are missing in an existing table so the user never has to run SQL
    migrations manually.
    """

    # --- connect without selecting a database first ---
    conn = pymysql.connect(
        host=Config.MYSQL_HOST,
        port=Config.MYSQL_PORT,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor,
    )
    cur = conn.cursor()

    # 1. Create database
    db_name = _safe_identifier(Config.MYSQL_DB)
    cur.execute(
        "CREATE DATABASE IF NOT EXISTS `%s` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        % db_name
    )
    cur.execute("USE `%s`" % db_name)

    # 2. Create tables (safe on fresh install)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(50) UNIQUE NOT NULL,
        password VARCHAR(255) NOT NULL,
        nama_lengkap VARCHAR(100) NOT NULL,
        role ENUM('admin','user','staff','manager','satpam','asman') NOT NULL DEFAULT 'staff',
        divisi VARCHAR(50),
        is_active TINYINT(1) DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS surat_izin (
        id INT AUTO_INCREMENT PRIMARY KEY,
        jenis ENUM('keluar','masuk') NOT NULL DEFAULT 'keluar',
        no_surat VARCHAR(100) NOT NULL,
        tanggal DATE NOT NULL,
        tgl_terbit DATE NOT NULL,
        divisi VARCHAR(50) NOT NULL,
        nama VARCHAR(100) NOT NULL,
        badge VARCHAR(50) NOT NULL,
        no_kendaraan VARCHAR(50) NOT NULL,
        perusahaan VARCHAR(100) NOT NULL,
        no_spk VARCHAR(100) NOT NULL,
        foto_ktp VARCHAR(255),
        file_spk VARCHAR(255),
        pemohon VARCHAR(100) NOT NULL,
        diperiksa_oleh VARCHAR(100) NOT NULL,
        disetujui_oleh VARCHAR(100) NOT NULL,
        barang_items TEXT NOT NULL,
        lampiran_foto TEXT,
        status ENUM('pending','review','approved','rejected') NOT NULL DEFAULT 'pending',
        catatan TEXT,
        approval_user ENUM('pending','sesuai','tidak_sesuai') DEFAULT 'pending',
        approval_user_by INT,
        approval_user_at TIMESTAMP NULL,
        approval_user_note TEXT,
        approval_satpam ENUM('pending','sesuai','tidak_sesuai') DEFAULT 'pending',
        approval_satpam_by INT,
        approval_satpam_at TIMESTAMP NULL,
        approval_satpam_note TEXT,
        approval_asman ENUM('pending','approved','rejected') DEFAULT 'pending',
        approval_asman_by INT,
        approval_asman_at TIMESTAMP NULL,
        approval_asman_note TEXT,
        approval_manager ENUM('pending','approved','rejected') DEFAULT 'pending',
        approval_manager_by INT,
        approval_manager_at TIMESTAMP NULL,
        approval_manager_note TEXT,
        created_by INT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_jenis (jenis),
        INDEX idx_no_surat (no_surat),
        INDEX idx_tanggal (tanggal),
        INDEX idx_status (status),
        INDEX idx_divisi (divisi)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS log_activity (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT,
        action VARCHAR(50) NOT NULL,
        description TEXT NOT NULL,
        ip_address VARCHAR(45),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_action (action),
        INDEX idx_created_at (created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT,
        title VARCHAR(200) NOT NULL,
        message TEXT NOT NULL,
        link VARCHAR(255),
        is_read TINYINT(1) DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_user_id (user_id),
        INDEX idx_is_read (is_read),
        INDEX idx_created_at (created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)

    conn.commit()

    # ------------------------------------------------------------------
    # 3. Auto-migrate: add any missing columns to existing tables
    #    This fixes the "Unknown column 'is_active'" error when the
    #    table was created by an older schema that lacked the column.
    # ------------------------------------------------------------------
    _migrate_table(cur, 'users', [
        ('is_active',       "TINYINT(1) DEFAULT 1 AFTER `divisi`"),
        ('role',            "ENUM('admin','staff','manager') NOT NULL DEFAULT 'staff' AFTER `nama_lengkap`"),
        ('divisi',          "VARCHAR(50) AFTER `role`"),
        ('updated_at',      "TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP AFTER `created_at`"),
    ])

    _migrate_table(cur, 'surat_izin', [
        ('jenis',           "ENUM('keluar','masuk') NOT NULL DEFAULT 'keluar' AFTER `id`"),
        ('status',          "ENUM('pending','review','approved','rejected') NOT NULL DEFAULT 'pending' AFTER `lampiran_foto`"),
        ('catatan',         "TEXT AFTER `status`"),
        ('created_by',      "INT AFTER `catatan`"),
        ('updated_at',      "TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP AFTER `created_at`"),
        ('approval_user',        "ENUM('pending','sesuai','tidak_sesuai') DEFAULT 'pending' AFTER `catatan`"),
        ('approval_user_by',     "INT AFTER `approval_user`"),
        ('approval_user_at',     "TIMESTAMP NULL AFTER `approval_user_by`"),
        ('approval_user_note',   "TEXT AFTER `approval_user_at`"),
        ('approval_satpam',      "ENUM('pending','sesuai','tidak_sesuai') DEFAULT 'pending' AFTER `approval_user_note`"),
        ('approval_satpam_by',   "INT AFTER `approval_satpam`"),
        ('approval_satpam_at',   "TIMESTAMP NULL AFTER `approval_satpam_by`"),
        ('approval_satpam_note', "TEXT AFTER `approval_satpam_at`"),
        ('approval_asman',       "ENUM('pending','approved','rejected') DEFAULT 'pending' AFTER `approval_satpam_note`"),
        ('approval_asman_by',    "INT AFTER `approval_asman`"),
        ('approval_asman_at',    "TIMESTAMP NULL AFTER `approval_asman_by`"),
        ('approval_asman_note',  "TEXT AFTER `approval_asman_at`"),
        ('approval_manager',     "ENUM('pending','approved','rejected') DEFAULT 'pending' AFTER `approval_asman_note`"),
        ('approval_manager_by',  "INT AFTER `approval_manager`"),
        ('approval_manager_at',  "TIMESTAMP NULL AFTER `approval_manager_by`"),
        ('approval_manager_note',"TEXT AFTER `approval_manager_at`"),
        ('foto_ktp',            "VARCHAR(255) AFTER `no_spk`"),
        ('file_spk',            "VARCHAR(255) AFTER `foto_ktp`"),
    ])

    # Ensure status ENUM includes 'review' for existing tables
    try:
        cur.execute(
            "ALTER TABLE `surat_izin` MODIFY COLUMN `status` "
            "ENUM('pending','review','approved','rejected') NOT NULL DEFAULT 'pending'"
        )
    except Exception:
        pass

    # Ensure users role ENUM includes user, satpam and asman
    try:
        cur.execute(
            "ALTER TABLE `users` MODIFY COLUMN `role` "
            "ENUM('admin','user','staff','manager','satpam','asman') NOT NULL DEFAULT 'staff'"
        )
    except Exception:
        pass

    # Ensure approval_user ENUM includes sesuai and tidak_sesuai
    try:
        cur.execute(
            "ALTER TABLE `surat_izin` MODIFY COLUMN `approval_user` "
            "ENUM('pending','sesuai','tidak_sesuai') DEFAULT 'pending'"
        )
    except Exception:
        pass

    conn.commit()

    # ------------------------------------------------------------------
    # 4. Seed default users if the table is empty
    # ------------------------------------------------------------------
    cur.execute("SELECT COUNT(*) AS c FROM users")
    if cur.fetchone()['c'] == 0:
        import bcrypt
        pw = bcrypt.hashpw(b'admin123', bcrypt.gensalt()).decode()
        cur.execute(
            "INSERT INTO users (username,password,nama_lengkap,role,divisi) VALUES (%s,%s,%s,%s,%s)",
            ('admin', pw, 'Administrator', 'admin', 'IT'),
        )
        pw2 = bcrypt.hashpw(b'staff123', bcrypt.gensalt()).decode()
        cur.execute(
            "INSERT INTO users (username,password,nama_lengkap,role,divisi) VALUES (%s,%s,%s,%s,%s)",
            ('staff01', pw2, 'Budi Santoso', 'staff', 'PEMELIHARAAN'),
        )
        pw3 = bcrypt.hashpw(b'manager123', bcrypt.gensalt()).decode()
        cur.execute(
            "INSERT INTO users (username,password,nama_lengkap,role,divisi) VALUES (%s,%s,%s,%s,%s)",
            ('manager01', pw3, 'Manager Administrasi', 'manager', 'ADMINISTRASI'),
        )
        pw4 = bcrypt.hashpw(b'satpam123', bcrypt.gensalt()).decode()
        cur.execute(
            "INSERT INTO users (username,password,nama_lengkap,role,divisi) VALUES (%s,%s,%s,%s,%s)",
            ('satpam01', pw4, 'Satpam Security', 'satpam', 'KEAMANAN'),
        )
        pw5 = bcrypt.hashpw(b'asman123', bcrypt.gensalt()).decode()
        cur.execute(
            "INSERT INTO users (username,password,nama_lengkap,role,divisi) VALUES (%s,%s,%s,%s,%s)",
            ('asman01', pw5, 'Asman Umum', 'asman', 'UMUM'),
        )
        pw6 = bcrypt.hashpw(b'user123', bcrypt.gensalt()).decode()
        cur.execute(
            "INSERT INTO users (username,password,nama_lengkap,role,divisi) VALUES (%s,%s,%s,%s,%s)",
            ('user01', pw6, 'User Pemberi Kerja', 'user', 'PEMELIHARAAN'),
        )

    # Seed sample surat if empty
    cur.execute("SELECT COUNT(*) AS c FROM surat_izin")
    if cur.fetchone()['c'] == 0:
        import json
        samples = [
            ('keluar', '3783.SJ/07/ADPPGU/2023', '2023-07-15', '2023-07-01',
             'PEMELIHARAAN', 'BUDI SANTOSO', 'EMP-12345', 'B 1234 XYZ',
             'PT MITRA SEJAHTERA', 'SPK/2023/07/001', 'BUDI SANTOSO',
             'KOMANDAN REGU', 'MANAGER ADMINISTRASI',
             json.dumps([
                 {"nama_barang": "Kabel Listrik 4x2.5mm", "jumlah": 10,
                  "satuan": "Roll", "keterangan": "Merah, panjang 100m"},
                 {"nama_barang": "MCB 3 Phase", "jumlah": 5,
                  "satuan": "Unit", "keterangan": "32A Schneider"},
             ]), None, 'approved', 1),
            ('masuk', '3784.SM/07/ADPPGU/2023', '2023-07-16', '2023-07-01',
             'OPERASI', 'SARI DEWI', 'EMP-67890', 'B 5678 ABC',
             'PT JAYA ABADI', 'SPK/2023/07/002', 'SARI DEWI',
             'SUPERVISOR OPERASI', 'MANAGER ADMINISTRASI',
             json.dumps([
                 {"nama_barang": "Transformator 500 kVA", "jumlah": 1,
                  "satuan": "Unit", "keterangan": "Baru"},
             ]), None, 'pending', 1),
            ('keluar', '3785.SJ/08/ADPPGU/2023', '2023-08-10', '2023-08-01',
             'TEKNIK', 'AGUS PRASETYA', 'EMP-24680', 'B 9012 DEF',
             'CV TEKNIK MANDIRI', 'MEMO/TEK/08/2023', 'AGUS PRASETYA',
             'KEPALA TEKNIK', 'MANAGER ADMINISTRASI',
             json.dumps([
                 {"nama_barang": "Multimeter Digital", "jumlah": 3,
                  "satuan": "Unit", "keterangan": "Fluke 87V"},
             ]), None, 'approved', 1),
        ]
        for s in samples:
            cur.execute("""
                INSERT INTO surat_izin
                (jenis,no_surat,tanggal,tgl_terbit,divisi,nama,badge,
                 no_kendaraan,perusahaan,no_spk,pemohon,diperiksa_oleh,
                 disetujui_oleh,barang_items,lampiran_foto,status,created_by)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, s)

    conn.commit()
    cur.close()
    conn.close()


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------

def _migrate_table(cur, table, columns):
    """Add *columns* to *table* when they do not already exist.

    ``columns`` is a list of ``(column_name, column_definition)`` tuples.
    ``column_definition`` should include the full MySQL column spec
    (type, default, AFTER clause, etc.).

    The function queries ``INFORMATION_SCHEMA.COLUMNS`` to see which
    columns are already present and only issues ``ALTER TABLE … ADD
    COLUMN`` for the missing ones.  This makes it completely safe to run
    on every application startup.
    """
    table = _safe_identifier(table)
    cur.execute(
        "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s",
        (Config.MYSQL_DB, table),
    )
    existing = {row['COLUMN_NAME'] for row in cur.fetchall()}

    for col_name, col_def in columns:
        col_name = _safe_identifier(col_name)
        if col_name not in existing:
            sql = "ALTER TABLE `%s` ADD COLUMN `%s` %s" % (table, col_name, col_def)
            cur.execute(sql)
            print(f"  ✅ Migrated: ALTER TABLE `{table}` ADD COLUMN `{col_name}`")
