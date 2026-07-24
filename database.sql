-- ============================================
-- DATABASE: surat_izin_db
-- Untuk Aplikasi Surat Izin Keluar Masuk Barang
-- PT PLN Indonesia Power
-- Indonesia Power Integrated Management System
-- ============================================

-- Buat database jika belum ada
CREATE DATABASE IF NOT EXISTS surat_izin_db
CHARACTER SET utf8mb4
COLATE utf8mb4_unicode_ci;

-- Gunakan database
USE surat_izin_db;

-- ============================================
-- TABEL: users
-- ============================================
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    nama_lengkap VARCHAR(100) NOT NULL,
    role ENUM('admin','user','staff','manager','satpam','asman','pemberi_kerja') NOT NULL DEFAULT 'staff',
    divisi VARCHAR(50),
    is_active TINYINT(1) DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_username (username),
    INDEX idx_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- TABEL: surat_izin
-- Menyimpan data surat izin keluar & masuk barang
-- ============================================
CREATE TABLE IF NOT EXISTS surat_izin (
    id INT AUTO_INCREMENT PRIMARY KEY,

    -- Jenis surat: keluar atau masuk
    jenis ENUM('keluar','masuk') NOT NULL DEFAULT 'keluar',

    -- Informasi Surat
    no_surat VARCHAR(100) NOT NULL,
    tanggal DATE NOT NULL,
    tgl_terbit DATE NOT NULL,
    divisi VARCHAR(50) NOT NULL,

    -- Data Pemohon
    nama VARCHAR(100) NOT NULL,
    badge VARCHAR(50) NOT NULL,
    no_kendaraan VARCHAR(50) NOT NULL,
    perusahaan VARCHAR(100) NOT NULL,
    no_spk VARCHAR(100) NOT NULL,

    -- Dokumen Pemohon
    foto_ktp VARCHAR(255),
    file_spk VARCHAR(255),

    -- Tanda Tangan
    pemohon VARCHAR(100) NOT NULL,
    diperiksa_oleh VARCHAR(100) NOT NULL,
    disetujui_oleh VARCHAR(100) NOT NULL,

    -- Data Barang (JSON)
    barang_items TEXT NOT NULL,

    -- Lampiran foto (nama file yang di-upload)
    lampiran_foto TEXT,

    -- Status persetujuan
    status ENUM('pending','review','approved','rejected') NOT NULL DEFAULT 'pending',
    catatan TEXT,

    -- Multi-stage approval (User -> Satpam -> Asman -> Manager)
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

    -- Flexible Approval Chain (JSON)
    approval_chain JSON COMMENT 'custom approval chain stages',

    -- Urgency Level
    urgency ENUM('normal','urgent') DEFAULT 'normal',

    -- Escalation
    is_escalated TINYINT(1) DEFAULT 0,
    escalation_level INT DEFAULT 0,

    -- QR Code Verification
    unique_hash VARCHAR(64) UNIQUE COMMENT 'for QR code verification',

    -- Relasi ke user pembuat
    created_by INT,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- Indexes
    INDEX idx_jenis (jenis),
    INDEX idx_no_surat (no_surat),
    INDEX idx_tanggal (tanggal),
    INDEX idx_divisi (divisi),
    INDEX idx_status (status),
    INDEX idx_nama (nama),
    INDEX idx_perusahaan (perusahaan),
    INDEX idx_created_by (created_by)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- TABEL: log_activity
-- ============================================
CREATE TABLE IF NOT EXISTS log_activity (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    action VARCHAR(50) NOT NULL,
    description TEXT NOT NULL,
    ip_address VARCHAR(45),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_action (action),
    INDEX idx_created_at (created_at),
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- TABEL: notifications
-- ============================================
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- TABEL: approval_delegations
-- Untuk sistem delegasi persetujuan
-- ============================================
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- TABEL: surat_settings
-- Untuk konfigurasi sistem approval
-- ============================================
CREATE TABLE IF NOT EXISTS surat_settings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    setting_key VARCHAR(100) UNIQUE NOT NULL,
    setting_value TEXT,
    description VARCHAR(255),
    updated_by INT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- TABEL: blacklist_items
-- Untuk anti-fraud: barang terlarang
-- ============================================
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- TABEL: api_keys
-- Untuk autentikasi API eksternal
-- ============================================
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- TABEL: audit_logs
-- Untuk audit trail persetujuan
-- ============================================
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- DATA DEFAULT SETTINGS
-- ============================================
INSERT IGNORE INTO surat_settings (setting_key, setting_value, description) VALUES
('approval_chain_normal', '["user", "satpam", "manager"]', 'Approval chain for normal items - without Asman'),
('approval_chain_urgent', '["manager"]', 'Fast track approval for urgent items'),
('approval_chain_full', '["user", "satpam", "asman", "manager"]', 'Full approval chain with Asman'),
('approval_chain_vendor', '["satpam", "manager"]', 'For known vendors - skip user approval'),
('high_value_threshold', '50000000', 'Minimum value requiring double manager approval'),
('reminder_hours_user', '4', 'Hours before sending reminder to user'),
('reminder_hours_satpam', '8', 'Hours before sending reminder to satpam'),
('reminder_hours_asman', '12', 'Hours before sending reminder to asman'),
('reminder_hours_manager', '24', 'Hours before sending reminder to manager'),
('escalation_hours', '48', 'Hours before escalating to admin'),
('blacklist_enabled', '1', 'Enable item blacklist check'),
('double_approval_threshold', '50000000', 'Value requiring 2 manager approvals'),
('forbidden_hours_start', '22:00', 'Forbidden hours start time'),
('forbidden_hours_end', '06:00', 'Forbidden hours end time'),
('forbidden_hours_enabled', '0', 'Enable forbidden hours restriction');

-- ============================================
-- DATA DEFAULT BLACKLIST ITEMS
-- ============================================
INSERT IGNORE INTO blacklist_items (item_name, item_pattern, reason) VALUES
('Senjata Api', '^senjata.*$', 'Barang terlarang untuk dibawa masuk'),
('Bahan Kimia Berbahaya', '^bahan.*kimia.*$', 'Bahan kimia tidak diizinkan');

-- ============================================
-- DATA DEFAULT USERS (password hash bcrypt)
-- ============================================
-- Default password: admin123, staff123, manager123, satpam123, asman123, user123, pk123
INSERT IGNORE INTO users (username, password, nama_lengkap, role, divisi) VALUES
('admin', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.xULvjF8BjCW2P2', 'Administrator', 'admin', 'IT'),
('staff01', '$2b$12$KIXxE1u1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.xULvjF8BjCW2P2', 'Budi Santoso', 'staff', 'PEMELIHARAAN'),
('manager01', '$2b$12$KIXxE1u1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.xULvjF8BjCW2P2', 'Manager Administrasi', 'manager', 'ADMINISTRASI'),
('satpam01', '$2b$12$KIXxE1u1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.xULvjF8BjCW2P2', 'Satpam Security', 'satpam', 'KEAMANAN'),
('asman01', '$2b$12$KIXxE1u1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.xULvjF8BjCW2P2', 'Asman Umum', 'asman', 'UMUM'),
('user01', '$2b$12$KIXxE1u1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.xULvjF8BjCW2P2', 'User Pemberi Kerja', 'user', 'PEMELIHARAAN'),
('pk01', '$2b$12$KIXxE1u1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.xULvjF8BjCW2P2', 'PIC Vendor Mitra', 'pemberi_kerja', 'VENDOR');

-- ============================================
-- Tampilkan semua tabel yang dibuat
-- ============================================
SHOW TABLES;
