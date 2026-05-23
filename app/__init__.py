# ==========================================
# Flask 工廠函數 - 應用初始化
# ==========================================
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config

# 初始化擴展實例
db = SQLAlchemy()
login_manager = LoginManager()


def create_app():
    """Flask 應用工廠函數"""
    
    # 創建應用（指定模板和靜態文件目錄）
    app = Flask(__name__, 
                template_folder='../templates',
                static_folder='../static')
    app.config.from_object(Config)
    
    # 初始化擴展
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = "⚠️ 偵測到未登入，請先進入會員系統以解鎖戰情室。"
    login_manager.login_message_category = "warning"
    
    # 設定日誌
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    logger = logging.getLogger(__name__)
    
    # 註冊藍圖
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.analysis import analysis_bp
    from app.routes.payment import payment_bp
    from app.routes.admin import admin_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(payment_bp)
    app.register_blueprint(admin_bp, url_prefix='')
    
    # 上下文處理器（注入變數到所有模板）
    @app.context_processor
    def inject_admin():
        return dict(admin_email=Config.ADMIN_EMAIL)
    
    # 使用者載入器
    from app.models import User
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # 建立資料表
    with app.app_context():
        db.create_all()
    
    logger.info("✅ Roger Quant SaaS 應用已啟動")
    
    return app
