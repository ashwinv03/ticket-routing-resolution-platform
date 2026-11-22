import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

class Config:
    """Base application configuration using lightweight SQLite."""
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-ticket-platform-local-2026')
    
    # PySQLite zero-overhead database file
    db_path = BASE_DIR / 'tickets.db'
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URI', f"sqlite:///{db_path}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Upload folder for ticket attachments
    UPLOAD_FOLDER = BASE_DIR / 'app' / 'static' / 'uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'txt', 'log', 'docx'}
    
    # Cloud LLM API Config
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
