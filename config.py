import os

from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv(os.path.join(os.path.abspath(os.path.dirname(__file__)), '.env'))

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

    # MySQL configuration — override via .env or environment variables
    MYSQL_HOST = os.environ.get('MYSQL_HOST', '127.0.0.1')
    MYSQL_PORT = int(os.environ.get('MYSQL_PORT', 3306))
    MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', 'password123')
    MYSQL_DB = os.environ.get('MYSQL_DB', 'surat_izin_db')

    PDF_DIR = os.path.join(BASE_DIR, 'static', 'pdfs')
    UPLOAD_DIR = os.path.join(BASE_DIR, 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    APP_NAME = 'Sistem Surat Izin Keluar Masuk Barang'
    COMPANY_NAME = 'PT PLN INDONESIA POWER'
    COMPANY_SUB = 'UBP Jawa Tengah 2 Adipala'
    SYSTEM_NAME = 'Indonesia Power Integrated Management System'
    DOC_NO = 'ADP.17.01.015'
    DOC_REV = '2'
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    ALLOWED_DOC_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'png', 'jpg', 'jpeg'}

    @staticmethod
    def init_app(app):
        for d in [Config.PDF_DIR, Config.UPLOAD_DIR]:
            os.makedirs(d, exist_ok=True)