from datetime import datetime
import os
import logging
from pathlib import Path

import pandas as pd
import markdown
from flask import Flask, jsonify, render_template, request, url_for, redirect, flash
from openai import OpenAI, OpenAIError
from dotenv import load_dotenv

# --- 🎯 導入商用 SaaS 會員驗證套件 ---
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

import stock_PE
import backtest_engine

# ==========================================
# 專業設定 1：初始化系統日誌 (Logging)
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ==========================================
# 專業設定 2：環境與核心服務實例化
# ==========================================
load_dotenv()
app = Flask(__name__)

# 🎯 SaaS 安全防護：設定 Session 秘密金鑰 (防篡改)
app.secret_key = os.getenv("SECRET_KEY", "RogerUltraSecureSaaSKey2026")

# 🎯 整合 Aiven 資料庫連線 (使用 SQLAlchemy ORM)
db_host = os.getenv("db_host", "").strip()
db_user = os.getenv("db_user", "").strip()
db_password = os.getenv("db_password", "").strip()
db_database = os.getenv("db_database", "").strip()
db_port = os.getenv("db_port", "21697").strip()

# 轉換為標準 SQLAlchemy 連線字串 (強制開啟 SSL 連線 Aiven)
app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_database}?ssl_ca="
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 實例化數據庫 ORM 與 登入管理器
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
# 設定未登入時，自動跳轉的頁面
login_manager.login_view = 'login'
login_manager.login_message = "⚠️ 偵測到未登入，請先進入會員系統以解鎖戰情室。"
login_manager.login_message_category = "warning"

# 確保從環境變數正確抓取 API Key
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

# 使用現代化 Pathlib 管理目錄
STATIC_IMG_DIR = Path(app.root_path) / "static" / "images"
STATIC_IMG_DIR.mkdir(parents=True, exist_ok=True)

# ==========================================
# 🎯 會員數據庫模型 (User Model)
# ==========================================
class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    is_vip = db.Column(db.Boolean, default=False)          # 商業權限開關
    quota_remaining = db.Column(db.Integer, default=5)     # 每日使用額度
    created_at = db.Column(db.DateTime, default=datetime.now)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# 啟動時自動檢查並建立 user 表
with app.app_context():
    try:
        db.create_all()
        logger.info("✅ Aiven 資料庫中的 users 會員表已就緒。")
    except Exception as e:
        logger.error(f"❌ 初始化 users 表失敗: {e}")


# ==========================================
# 核心服務：AI 報告生成器
# ==========================================
def generate_ai_report(stock_id: str, df: pd.DataFrame) -> str:
    try:
        if df is None or df.empty:
            return "<p style='color:#E63946;'><strong>⚠️ 無法取得資料庫數據。</strong></p>"

        df = df.copy() 
        df['date'] = pd.to_datetime(df['date'], format='%Y-%m-%d', errors='coerce')
        df = df.dropna(subset=['date'])
        
        df_sorted = df.sort_values('date')
        report_data = df_sorted.tail(20).to_string()

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "你是一位精通台股的價值投資分析師。請使用 Markdown 格式。"},
                {"role": "user", "content": f"分析代號 {stock_id} 最新數據：\n{report_data}"}
            ],
            timeout=45 
        )
        return markdown.markdown(response.choices[0].message.content)
    except Exception as e:
        return f"<p style='color:#E63946;'><strong>⚠️ AI 分析出錯：{str(e)}</strong></p>"


# ==========================================
# 🎯 會員註冊與登入路由 (Auth Logic)
# ==========================================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        email = request.form.get('email').strip()
        password = request.form.get('password').strip()
        if User.query.filter_by(email=email).first():
            flash("❌ 該 Email 已經註冊過，請直接登入。", "danger")
            return redirect(url_for('register'))
        new_user = User(email=email)
        new_user.set_password(password)
        new_user.is_vip = True # 推廣期註冊預設開啟 VIP
        db.session.add(new_user)
        db.session.commit()
        flash("✅ 註冊成功！請登入體驗完整功能。", "success")
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        email = request.form.get('email').strip()
        password = request.form.get('password').strip()
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user, remember=True)
            flash("✅ 歡迎回來！戰情系統已成功解鎖。", "success")
            return redirect(url_for('index'))
        else:
            flash("❌ Email 或密碼錯誤，請重新檢查。", "danger")
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("您已成功登出。", "info")
    return redirect(url_for('login'))


# ==========================================
# Web 路由設計 (含權限保護)
# ==========================================
@app.route('/', methods=['GET'])
def index():
    # 這是你的「完美首頁」入口，目前可先維持公開，或引導至登入
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
@login_required # 🎯 保護 API：必須登入才能請求分析
def analyze():
    stock_id = request.form.get('stock_id', '').strip()
    if not stock_id:
        return "❌ 錯誤：請輸入股票代號！", 400
    try:
        chart_json_data = stock_PE.get_echarts_data(stock_id)
        if not chart_json_data:
            return f"❌ 找不到股票 {stock_id} 的數據。", 404
        df = stock_PE.get_stock_data(stock_id)
        ai_html_report = generate_ai_report(stock_id, df)
        return render_template('result.html', stock_id=stock_id, chart_data=chart_json_data, ai_report=ai_html_report)
    except Exception as e:
        return f"❌ 伺服器處理失敗: {str(e)}", 500

@app.route('/analyze')
@login_required # 🎯 保護頁面
def analyzes():
    return render_template('analyze.html')

@app.route('/backtest')
@login_required # 🎯 保護頁面
def backtest_page():
    return render_template('backtest.html')

@app.route('/api/run_backtest', methods=['POST'])
@login_required # 🎯 保護 API
def api_run_backtest():
    data = request.get_json() or {}
    ticker = data.get('ticker', '2330.TW')
    today_str = datetime.now().strftime('%Y-%m-%d')
    start_date = data.get('start_date', '2000-01-01')
    end_date = data.get('end_date', today_str)
    result = backtest_engine.run_backtest_json(ticker=ticker, start_date=start_date, end_date=end_date)
    return jsonify(result), 200

# ==========================================
# 啟動服務
# ==========================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"🚀 SaaS 戰情終端啟動中... Port: {port}")
    app.run(host='0.0.0.0', port=port)