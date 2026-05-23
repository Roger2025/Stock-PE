# ==========================================
# Roger Quant - SaaS 設定集中管理
# ==========================================
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """基礎設定"""
    
    # Flask 核心
    SECRET_KEY = os.getenv("SECRET_KEY", "RogerUltraSecureSaaSKey2026")
    
    # 資料庫
    DB_HOST = os.getenv("db_host", "").strip()
    DB_USER = os.getenv("db_user", "").strip()
    DB_PASSWORD = os.getenv("db_password", "").strip()
    DB_DATABASE = os.getenv("db_database", "").strip()
    DB_PORT = os.getenv("db_port", "21697").strip()
    
    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_DATABASE}?ssl_ca="
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    
    # 管理員
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "A127038349@gmail.com").strip()
    
    # 基礎 URL
    BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:10000").strip()
    
    # 綠界金流
    ECPAY_MERCHANT_ID = os.getenv("ECPAY_MERCHANT_ID", "2000132").strip()
    ECPAY_HASH_KEY = os.getenv("ECPAY_HASH_KEY", "5294y06JbISpM5x9").strip()
    ECPAY_HASH_IV = os.getenv("ECPAY_HASH_IV", "v77hoKGq4kWxNNIS").strip()
