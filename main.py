# 🚀 置頂載入環境變數
from dotenv import load_dotenv
load_dotenv()

from datetime import datetime
import os
import logging
import random
import string
from pathlib import Path
from functools import wraps

import pandas as pd
import markdown
from flask import Flask, jsonify, render_template, request, url_for, redirect, flash
from openai import OpenAI, OpenAIError

# --- 🎯 導入商用 SaaS 會員驗證與金流套件 ---
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# 引入綠界 SDK 實體檔案
import ecpay_payment_sdk

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
app = Flask(__name__)

# 🎯 SaaS 安全防護：設定 Session 秘密金鑰
app.secret_key = os.getenv("SECRET_KEY", "RogerUltraSecureSaaSKey2026")

# 🎯 整合 Aiven 資料庫連線
db_host = os.getenv("db_host", "").strip()
db_user = os.getenv("db_user", "").strip()
db_password = os.getenv("db_password", "").strip()
db_database = os.getenv("db_database", "").strip()
db_port = os.getenv("db_port", "21697").strip()

app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_database}?ssl_ca="
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = "⚠️ 偵測到未登入，請先進入會員系統以解鎖戰情室。"
login_manager.login_message_category = "warning"

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:10000").strip()

# ==========================================
# 🎯 會員與訂單數據庫模型 (支援完整生命週期時間戳版)
# ==========================================
class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    merchant_trade_no = db.Column(db.String(50), unique=True, nullable=False) 
    amount = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='pending') 
    created_at = db.Column(db.DateTime, default=datetime.now)

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    is_vip = db.Column(db.Boolean, default=False)
    quota_remaining = db.Column(db.Integer, default=5)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    # 🚀 升級新增：精準追蹤會員付費與退訂生命週期
    vip_since = db.Column(db.DateTime, nullable=True)     # 開通 VIP 的準確時間
    canceled_at = db.Column(db.DateTime, nullable=True)   # 取消/降級 VIP 的準確時間
    
    orders = db.relationship('Order', backref='user', lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# 系統啟動時自動檢查並建立新欄位 (若表格已存在，SQLAlchemy 預設不會自動加欄位，建議看下方說明)
with app.app_context():
    db.create_all()

# ==========================================
# 🛡️ SaaS 創辦人絕對領域與權限防護設定
# ==========================================
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "A127038349@gmail.com").strip()

@app.context_processor
def inject_admin():
    return dict(admin_email=ADMIN_EMAIL)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.email != ADMIN_EMAIL:
            flash("⛔ 越權存取攔截：您不具備總管中台的存取權限。", "danger")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# ==========================================
# 🎯 核心功能：AI 報告生成
# ==========================================
def generate_ai_report(stock_id: str, df: pd.DataFrame) -> str:
    try:
        if df is None or df.empty:
            return "<p style='color:#E63946;'><strong>⚠️ 無法取得資料庫數據。</strong></p>"
        
        df_clean = df.copy()
        df_clean['date'] = df_clean['date'].astype(str)
        
        df_sorted = df_clean.sort_values('date')
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
# 🎯 路由設計：會員系統
# ==========================================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated: return redirect(url_for('index'))
    if request.method == 'POST':
        email = request.form.get('email').strip()
        password = request.form.get('password').strip()
        if User.query.filter_by(email=email).first():
            flash("❌ 該 Email 已經註冊過。", "danger")
            return redirect(url_for('register'))
        new_user = User(email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash("✅ 註冊成功！請登入解鎖功能。", "success")
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('index'))
    if request.method == 'POST':
        email = request.form.get('email').strip()
        password = request.form.get('password').strip()
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user, remember=True)
            flash("✅ 歡迎回來！戰情系統已成功解鎖。", "success")
            return redirect(url_for('index'))
        flash("❌ Email 或密碼錯誤。", "danger")
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ==========================================
# 🎯 路由設計：金流變現系統 (ECPay)
# ==========================================
@app.route('/pricing')
@login_required
def pricing():
    return render_template('pricing.html')

@app.route('/checkout', methods=['POST'])
@login_required
def checkout():
    ECPAY_MERCHANT_ID = os.getenv("ECPAY_MERCHANT_ID", "2000132").strip()
    ECPAY_HASH_KEY = os.getenv("ECPAY_HASH_KEY", "5294y06JbISpM5x9").strip()
    ECPAY_HASH_IV = os.getenv("ECPAY_HASH_IV", "v77hoKGq4kWxNNIS").strip()

    trade_no = "RG" + datetime.now().strftime("%Y%m%d%H%M%S") + "".join(random.choices(string.ascii_uppercase, k=2))
    amount = 888 
    
    new_order = Order(user_id=current_user.id, merchant_trade_no=trade_no, amount=amount)
    db.session.add(new_order)
    db.session.commit()
    
    ecpay_sdk = ecpay_payment_sdk.ECPayPaymentSdk(
        MerchantID=ECPAY_MERCHANT_ID,
        HashKey=ECPAY_HASH_KEY,
        HashIV=ECPAY_HASH_IV
    )
    
    order_params = {
        'MerchantTradeNo': trade_no,
        'MerchantTradeDate': datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
        'PaymentType': 'aio',
        'TotalAmount': amount,
        'TradeDesc': 'Roger SaaS VIP 尊榮開通方案',
        'ItemName': '量化戰情室 Pro 終身權限',
        'ReturnURL': f"{BASE_URL}/ecpay_callback",       
        'OrderResultURL': f"{BASE_URL}/payment_result",   
        'ChoosePayment': 'ALL',
        'EncryptType': 1,
    }
    
    try:
        final_order_params = ecpay_sdk.create_order(order_params)
        action_url = "https://payment-stage.ecpay.com.tw/Cashier/AioCheckOut/V5"
        auto_submit_html = ecpay_sdk.gen_html_post_form(action_url, final_order_params)
        return auto_submit_html
    except Exception as e:
        logger.error(f"❌ 建立綠界跳轉表單失敗: {e}")
        return "金流系統連接異常，請檢查伺服器日誌。", 500

@app.route('/ecpay_callback', methods=['POST'])
def ecpay_callback():
    ECPAY_MERCHANT_ID = os.getenv("ECPAY_MERCHANT_ID", "2000132").strip()
    ECPAY_HASH_KEY = os.getenv("ECPAY_HASH_KEY", "5294y06JbISpM5x9").strip()
    ECPAY_HASH_IV = os.getenv("ECPAY_HASH_IV", "v77hoKGq4kWxNNIS").strip()

    data = request.form.to_dict()
    ecpay_sdk = ecpay_payment_sdk.ECPayPaymentSdk(
        MerchantID=ECPAY_MERCHANT_ID,
        HashKey=ECPAY_HASH_KEY,
        HashIV=ECPAY_HASH_IV
    )
    
    if ecpay_sdk.generate_check_mac_value(data) == data.get('CheckMacValue'):
        if data.get('RtnCode') == '1':
            trade_no = data.get('MerchantTradeNo')
            order = Order.query.filter_by(merchant_trade_no=trade_no).first()
            if order and order.status == 'pending':
                order.status = 'paid'
                user = User.query.get(order.user_id)
                user.is_vip = True
                # 🚀 自動化進帳監控：綠界確認收款當下，精準押上 VIP 生效時間戳記，並清空退訂紀錄
                user.vip_since = datetime.now()
                user.canceled_at = None
                db.session.commit()
                logger.info(f"💰 訂單 {trade_no} 成功收款！會員 {user.email} 於 {user.vip_since} 啟用 Pro 權限！")
        return '1|OK'
    return '0|Error'

@app.route('/payment_result')
@login_required
def payment_result():
    flash("🎉 綠界付款流程完成！系統正透過專屬加密通道同步升級您的帳號，請稍候刷新頁面。", "success")
    return redirect(url_for('index'))

# ==========================================
# 👑 路由設計：創辦人管理中台 (Admin Console)
# ==========================================
@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    total_users = User.query.count()
    vip_users = User.query.filter_by(is_vip=True).count()
    
    paid_orders = Order.query.filter_by(status='paid').all()
    total_gmv = sum(o.amount for o in paid_orders)
    
    users = User.query.order_by(User.created_at.desc()).limit(50).all()
    orders = Order.query.order_by(Order.created_at.desc()).limit(50).all()
    
    return render_template(
        'admin.html', 
        total_users=total_users, 
        vip_users=vip_users, 
        total_gmv=total_gmv, 
        users=users, 
        orders=orders
    )

@app.route('/admin/toggle_vip/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def admin_toggle_vip(user_id):
    target_user = User.query.get_or_404(user_id)
    
    if target_user.email == ADMIN_EMAIL:
        flash("⚠️ 安全鎖生效：創辦人無法隨意降級自身總管權限。", "warning")
        return redirect(url_for('admin_dashboard'))
        
    target_user.is_vip = not target_user.is_vip
    
    # 🚀 總管介入自動化感知邏輯：
    if target_user.is_vip:
        # 手動晉升 VIP：押上開通時間，抹除退訂紀錄
        target_user.vip_since = datetime.now()
        target_user.canceled_at = None
        action_text = "晉升尊榮 VIP (已記錄生效時間)"
    else:
        # 手動降級普通用戶：押上退訂/終止時間
        target_user.canceled_at = datetime.now()
        action_text = "降級為普通帳號 (已記錄退訂時間)"
        
    db.session.commit()
    logger.info(f"🛠️ 總管覆寫：會員 {target_user.email} 權限已 {action_text}")
    flash(f"✅ 成功將帳號 {target_user.email} {action_text}！", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_user(user_id):
    target_user = User.query.get_or_404(user_id)
    
    if target_user.email == ADMIN_EMAIL:
        flash("⛔ 致命攔截：系統嚴禁刪除創辦人總管核心帳號。", "danger")
        return redirect(url_for('admin_dashboard'))
        
    deleted_email = target_user.email
    db.session.delete(target_user)
    db.session.commit()
    
    logger.warning(f"💥 總管執行核爆指令：已徹底抹除會員 {deleted_email} 及其連動數據。")
    flash(f"💥 已將帳號 {deleted_email} 從系統資料庫徹底銷毀！", "success")
    return redirect(url_for('admin_dashboard'))

# ==========================================
# 🎯 路由設計：戰情功能
# ==========================================
@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
@login_required
def analyze():
    stock_id = request.form.get('stock_id', '').strip()
    if not stock_id: return "❌ 請輸入代號", 400
    try:
        chart_json_data = stock_PE.get_echarts_data(stock_id)
        df = stock_PE.get_stock_data(stock_id)
        ai_html_report = generate_ai_report(stock_id, df)
        return render_template('result.html', stock_id=stock_id, chart_data=chart_json_data, ai_report=ai_html_report)
    except Exception as e:
        return f"❌ 處理失敗: {str(e)}", 500

@app.route('/analyze')
@login_required
def analyzes():
    return render_template('analyze.html')

@app.route('/backtest')
@login_required
def backtest_page():
    return render_template('backtest.html')

@app.route('/api/run_backtest', methods=['POST'])
@login_required
def api_run_backtest():
    data = request.get_json() or {}
    ticker = data.get('ticker', '2330.TW')
    start_date = data.get('start_date', '2000-01-01')
    end_date = data.get('end_date', datetime.now().strftime('%Y-%m-%d'))
    result = backtest_engine.run_backtest_json(ticker=ticker, start_date=start_date, end_date=end_date)
    return jsonify(result), 200

if __name__ == "__main__":  
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))