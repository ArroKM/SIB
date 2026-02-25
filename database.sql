-- ============================================
-- DATABASE: surat_izin_db
-- Untuk Aplikasi Surat Izin Keluar Masuk Barang
-- PT PLN Indonesia Power
-- ============================================

-- Buat database jika belum ada
CREATE DATABASE IF NOT EXISTS surat_izin_db 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

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
    role ENUM('admin','user','staff','manager','satpam','asman') NOT NULL DEFAULT 'staff',
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
    INDEX idx_perusahaan (perusahaan)
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
-- TABEL: settings
-- ============================================
CREATE TABLE IF NOT EXISTS settings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    setting_key VARCHAR(50) UNIQUE NOT NULL,
    setting_value TEXT NOT NULL,
    description VARCHAR(255),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Data default settings
INSERT IGNORE INTO settings (setting_key, setting_value, description) VALUES
('company_name', 'PT PLN INDONESIA POWER', 'Nama Perusahaan'),
('company_address', 'UBP Jawa Tengah 2 Adipala', 'Alamat Perusahaan'),
('system_name', 'Indonesia Power Integrated Management System', 'Nama Sistem'),
('document_no', 'ADP.17.01.015', 'Nomor Dokumen'),
('revision', '2', 'Revisi Dokumen');

-- ============================================
-- DATA CONTOH (users akan di-seed oleh aplikasi via init_db)
-- ============================================

-- Tampilkan semua tabel yang dibuat
SHOW TABLES;