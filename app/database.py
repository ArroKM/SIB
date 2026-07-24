"""
Database module.
Handles database connections and initialization.
"""
import re
from datetime import datetime

import pymysql
import pymysql.cursors

from app.config import Config


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

    # 2b. Create new tables for enhanced features
    # Approval Delegations Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS approval_delegations (
        id INT AUTO_INCREMENT PRIMARY KEY,
        delegator_id INT NOT NULL,
        delegate_id INT NOT NULL,
        stages JSON NOT NULL COMMENT 'stages: user,satpam,asman,manager',
        start_date DATE NOT NULL,
        end_date DATE NOT NULL,
        is_active TINYINT(1) DEFAULT 1,
        reason VARCHAR(255),
        created_by INT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_delegator (delegator_id),
        INDEX idx_delegate (delegate_id),
        INDEX idx_dates (start_date, end_date)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)

    # Surat Settings Table (for approval chains)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS surat_settings (
        id INT AUTO_INCREMENT PRIMARY KEY,
        setting_key VARCHAR(100) UNIQUE NOT NULL,
        setting_value TEXT,
        description VARCHAR(255),
        updated_by INT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)

    # Blacklist Items Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS blacklist_items (
        id INT AUTO_INCREMENT PRIMARY KEY,
        item_name VARCHAR(200) NOT NULL,
        item_pattern VARCHAR(200) COMMENT 'regex pattern for matching',
        reason VARCHAR(255),
        is_active TINYINT(1) DEFAULT 1,
        created_by INT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_item_name (item_name),
        INDEX idx_active (is_active)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)

    # API Keys Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS api_keys (
        id INT AUTO_INCREMENT PRIMARY KEY,
        api_key VARCHAR(64) UNIQUE NOT NULL,
        client_name VARCHAR(100) NOT NULL,
        description VARCHAR(255),
        permissions JSON COMMENT 'allowed endpoints',
        is_active TINYINT(1) DEFAULT 1,
        last_used_at TIMESTAMP NULL,
        created_by INT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_api_key (api_key),
        INDEX idx_active (is_active)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)

    # Enhanced Audit Log Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INT AUTO_INCREMENT PRIMARY KEY,
        surat_id INT,
        user_id INT,
        action VARCHAR(50) NOT NULL,
        stage VARCHAR(20) COMMENT 'user,satpam,asman,manager',
        description TEXT,
        old_value JSON,
        new_value JSON,
        ip_address VARCHAR(45),
        user_agent VARCHAR(500),
        note TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_surat (surat_id),
        INDEX idx_user (user_id),
        INDEX idx_action (action),
        INDEX idx_created (created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)

    conn.commit()

    # ------------------------------------------------------------------
    # 3. Auto-migrate: add any missing columns to existing tables
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

    # Ensure users role ENUM includes pemberi_kerja
    try:
        cur.execute(
            "ALTER TABLE `users` MODIFY COLUMN `role` "
            "ENUM('admin','user','staff','manager','satpam','asman','pemberi_kerja') NOT NULL DEFAULT 'staff'"
        )
    except Exception:
        pass

    # New migrations for enhanced features
    _migrate_table(cur, 'surat_izin', [
        ('approval_chain', "JSON COMMENT 'custom approval chain'"),
        ('urgency', "ENUM('normal','urgent') DEFAULT 'normal'"),
        ('is_escalated', "TINYINT(1) DEFAULT 0"),
        ('escalation_level', "INT DEFAULT 0"),
        ('unique_hash', "VARCHAR(64) UNIQUE COMMENT 'for QR code verification'"),
    ])

    # Ensure approval_user ENUM includes sesuai and tidak_sesuai
    try:
        cur.execute(
            "ALTER TABLE `surat_izin` MODIFY COLUMN `approval_user` "
            "ENUM('pending','sesuai','tidak_sesuai') DEFAULT 'pending'"
        )
    except Exception:
        pass

    # Ensure approval_satpam ENUM includes sesuai and tidak_sesuai
    try:
        cur.execute(
            "ALTER TABLE `surat_izin` MODIFY COLUMN `approval_satpam` "
            "ENUM('pending','sesuai','tidak_sesuai') DEFAULT 'pending'"
        )
    except Exception:
        pass

    # Seed default settings
    cur.execute("SELECT COUNT(*) AS c FROM surat_settings")
    if cur.fetchone()['c'] == 0:
        import json
        # Default approval chains
        default_settings = [
            ('approval_chain_normal', json.dumps(['user', 'satpam', 'manager']),
             'Approval chain for normal items - without Asman'),
            ('approval_chain_urgent', json.dumps(['manager']),
             'Fast track approval for urgent items'),
            ('approval_chain_full', json.dumps(['user', 'satpam', 'asman', 'manager']),
             'Full approval chain with Asman'),
            ('approval_chain_vendor', json.dumps(['satpam', 'manager']),
             'For known vendors - skip user approval'),
            ('high_value_threshold', '50000000',
             'Minimum value requiring double manager approval'),
            ('reminder_hours_user', '4',
             'Hours before sending reminder to user'),
            ('reminder_hours_satpam', '8',
             'Hours before sending reminder to satpam'),
            ('reminder_hours_asman', '12',
             'Hours before sending reminder to asman'),
            ('reminder_hours_manager', '24',
             'Hours before sending reminder to manager'),
            ('escalation_hours', '48',
             'Hours before escalating to admin'),
            ('blacklist_enabled', '1',
             'Enable item blacklist check'),
            ('double_approval_threshold', '50000000',
             'Value requiring 2 manager approvals'),
            ('forbidden_hours_start', '22:00',
             'Forbidden hours start time'),
            ('forbidden_hours_end', '06:00',
             'Forbidden hours end time'),
            ('forbidden_hours_enabled', '0',
             'Enable forbidden hours restriction'),
        ]
        for key, value, desc in default_settings:
            cur.execute(
                "INSERT INTO surat_settings (setting_key, setting_value, description) VALUES (%s,%s,%s)",
                (key, value, desc)
            )

    # Seed blacklist items if empty
    cur.execute("SELECT COUNT(*) AS c FROM blacklist_items")
    if cur.fetchone()['c'] == 0:
        blacklist_items = [
            ('Senjata Api', r'^senjata.*$', 'Barang terlarang untuk dibawa masuk'),
            ('Bahan Kimia Berbahaya', r'^bahan.*kimia.*$', 'Bahan kimia tidak diizinkan'),
        ]
        for name, pattern, reason in blacklist_items:
            cur.execute(
                "INSERT INTO blacklist_items (item_name, item_pattern, reason) VALUES (%s,%s,%s)",
                (name, pattern, reason)
            )

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
        pw7 = bcrypt.hashpw(b'pk123', bcrypt.gensalt()).decode()
        cur.execute(
            "INSERT INTO users (username,password,nama_lengkap,role,divisi) VALUES (%s,%s,%s,%s,%s)",
            ('pk01', pw7, 'PIC Vendor Mitra', 'pemberi_kerja', 'VENDOR'),
        )

    def generate_seed_hash(surat_id, no_surat):
        """Generate unique hash for seed data (matches approval_helpers.generate_unique_hash)"""
        import hashlib
        hash_input = f"{surat_id}-{no_surat}-{datetime.now().isoformat()}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:32]

    # Seed sample surat if empty
    cur.execute("SELECT COUNT(*) AS c FROM surat_izin")
    if cur.fetchone()['c'] == 0:
        import json

        # Sample surat data - hashes will be generated after insert with proper IDs
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
             ]), None, 'approved', 'normal', 1),
            ('masuk', '3784.SM/07/ADPPGU/2023', '2023-07-16', '2023-07-01',
             'OPERASI', 'SARI DEWI', 'EMP-67890', 'B 5678 ABC',
             'PT JAYA ABADI', 'SPK/2023/07/002', 'SARI DEWI',
             'SUPERVISOR OPERASI', 'MANAGER ADMINISTRASI',
             json.dumps([
                 {"nama_barang": "Transformator 500 kVA", "jumlah": 1,
                  "satuan": "Unit", "keterangan": "Baru"},
             ]), None, 'pending', 'normal', 1),
            ('keluar', '3785.SJ/08/ADPPGU/2023', '2023-08-10', '2023-08-01',
             'TEKNIK', 'AGUS PRASETYA', 'EMP-24680', 'B 9012 DEF',
             'CV TEKNIK MANDIRI', 'MEMO/TEK/08/2023', 'AGUS PRASETYA',
             'KEPALA TEKNIK', 'MANAGER ADMINISTRASI',
             json.dumps([
                 {"nama_barang": "Multimeter Digital", "jumlah": 3,
                  "satuan": "Unit", "keterangan": "Fluke 87V"},
             ]), None, 'approved', 'urgent', 1),
            ('keluar', '3786.SJ/09/ADPPGU/2023', '2023-09-05', '2023-09-01',
             'ADMINISTRASI', 'DENI RAHMAT', 'EMP-11111', 'B 3333 GHI',
             'PT SUKSES MANDIRI', 'SPK/2023/09/001', 'DENI RAHMAT',
             'KEPALA ADMIN', 'MANAGER ADMINISTRASI',
             json.dumps([
                 {"nama_barang": "Laptop HP ProBook 450", "jumlah": 2,
                  "satuan": "Unit", "keterangan": "Untuk divisi baru"},
                 {"nama_barang": "Monitor LED 24 inch", "jumlah": 2,
                  "satuan": "Unit", "keterangan": "Dell UltraSharp"},
             ]), None, 'review', 'normal', 1),
            ('masuk', '3787.SM/10/ADPPGU/2023', '2023-10-12', '2023-10-01',
             'GUDANG', 'RINA KUSUMA', 'EMP-22222', 'B 7777 JKL',
             'PT LOGISTIK INDONESIA', 'DO/2023/10/001', 'RINA KUSUMA',
             'KEPALA GUDANG', 'MANAGER ADMINISTRASI',
             json.dumps([
                 {"nama_barang": "Suku Cadang Turbin", "jumlah": 20,
                  "satuan": "Pcs", "keterangan": " Untuk pemeliharaan PLTA"},
                 {"nama_barang": "Oli Turbine Oil", "jumlah": 5,
                  "satuan": "Drum", "keterangan": "Mobil SHC 626"},
             ]), None, 'approved', 'full', 1),
        ]

        # Insert sample surat
        cur.executemany("""
            INSERT INTO surat_izin
            (jenis,no_surat,tanggal,tgl_terbit,divisi,nama,badge,
             no_kendaraan,perusahaan,no_spk,pemohon,diperiksa_oleh,
             disetujui_oleh,barang_items,lampiran_foto,status,urgency,created_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, samples)

        # Update unique_hash for each inserted surat
        cur.execute("SELECT id, no_surat FROM surat_izin ORDER BY id")
        for row in cur.fetchall():
            hash_value = generate_seed_hash(row['id'], row['no_surat'])
            cur.execute(
                "UPDATE surat_izin SET unique_hash = %s WHERE id = %s",
                (hash_value, row['id'])
            )

    # Migration: Update unique_hash for existing surat without hash
    cur.execute("SELECT id, no_surat FROM surat_izin WHERE unique_hash IS NULL OR unique_hash = ''")
    existing_without_hash = cur.fetchall()
    if existing_without_hash:
        for row in existing_without_hash:
            hash_value = generate_seed_hash(row['id'], row['no_surat'])
            cur.execute(
                "UPDATE surat_izin SET unique_hash = %s WHERE id = %s",
                (hash_value, row['id'])
            )
        print(f"  ✅ Generated QR hashes for {len(existing_without_hash)} existing surat")

    conn.commit()
    cur.close()
    conn.close()


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------

def _migrate_table(cur, table, columns):
    """Add *columns* to *table* when they do not already exist."""
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
