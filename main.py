# 🚀 置頂載入環境變數
from dotenv import load_dotenv
load_dotenv()

from datetime import datetime, timedelta
import os
import logging
import random
import string
from pathlib import Path
from functools import wraps

import pandas as pd
import markdown
from flask import Flask, jsonify, render_template, request, url_for, redirect, flash
from sqlalchemy import text
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
    nickname = db.Column(db.String(100), nullable=True) # 🚀 新增個人化暱稱欄位
    password_hash = db.Column(db.String(256), nullable=False)
    is_vip = db.Column(db.Boolean, default=False)
    quota_remaining = db.Column(db.Integer, default=5)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    # 🚀 升級新增：精準追蹤會員付費與退訂生命週期
    vip_since = db.Column(db.DateTime, nullable=True)     # 開通 VIP 的準確時間
    canceled_at = db.Column(db.DateTime, nullable=True)   # 取消/降級 VIP 的準確時間
    vip_expires_at = db.Column(db.DateTime, nullable=True)  # 訂閱到期日（月付/年付用)
    
    orders = db.relationship('Order', backref='user', lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def current_plan_name(self):
        # 🚀 創辦人絕對識別
        from flask import current_app
        admin_email = current_app.jinja_env.globals.get('admin_email', 'A127038349@gmail.com')
        if self.email.lower().strip() == admin_email.lower().strip():
            return "系統創辦人"
            
        if not self.is_vip:
            return "普通用戶"
        # 判斷是否為終身版（無到期日代表永久買斷）
        if self.vip_since and not self.vip_expires_at:
            return "Pro 終身版"
        # 透過時間差判斷年付或月付
        if self.vip_since and self.vip_expires_at:
            days_diff = (self.vip_expires_at - self.vip_since).days
            if days_diff > 300:
                return "Pro 年費版"
            return "Pro 月費版"
        return "Pro 尊榮版"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ==========================================
# 專業設定 3：系統資料表掛載
# ==========================================
with app.app_context():
    db.create_all()
    # 歷史欄位遷移與洗資料邏輯已於 2026-05-13 順利執行完畢並封存
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
        if not current_user.is_authenticated or current_user.email.lower().strip() != ADMIN_EMAIL.lower().strip():
            flash("⛔ 越權存取攔截：您不具備總管中台的存取權限。", "danger")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# 🚀 升級新增：Pro VIP 專屬功能防護牆 (支援創辦人無條件穿透)
def vip_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        # 創辦人免驗證直接放行
        if current_user.email.lower().strip() == ADMIN_EMAIL.lower().strip():
            return f(*args, **kwargs)
            
        if not current_user.is_vip:
            flash("👑 此為 Pro 專屬功能！請先升級方案以解鎖個股深度分析與量化回測引擎。", "warning")
            return redirect(url_for('pricing'))
        return f(*args, **kwargs)
    return decorated_function

# ==========================================
# 🎯 核心功能：AI 報告生成 (極致純淨小數點修正版)
# ==========================================
def generate_ai_report(stock_id: str, df: pd.DataFrame) -> str:
    try:
        if df is None or df.empty:
            return "<p style='color:#E63946;'><strong>⚠️ 無法取得資料庫數據。</strong></p>"
        
        # 🚀 強制清洗數據流：過濾出數值欄位並統一四捨五入至小數點第二位
        df_clean = df.copy()
        for col in df_clean.select_dtypes(include=['float64', 'float32']).columns:
            df_clean[col] = df_clean[col].round(2)
            
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
# 🎯 路由設計：會員系統 (雙重密碼與暱稱驗證版)
# ==========================================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated: return redirect(url_for('index'))
    if request.method == 'POST':
        nickname = request.form.get('nickname', '').strip()
        email = request.form.get('email').strip()
        password = request.form.get('password').strip()
        confirm_password = request.form.get('confirm_password').strip() # 🚀 二次密碼核對

        if password != confirm_password:
            flash("❌ 兩次輸入的密碼不一致，請重新確認。", "danger")
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash("❌ 該 Email 已經註冊過。", "danger")
            return redirect(url_for('register'))

        # 預設賦予創始暱稱防呆
        if not nickname:
            nickname = email.split('@')[0]

        new_user = User(email=email, nickname=nickname)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash(f"✅ 歡迎 {nickname}！專屬帳號創建成功，請登入以啟動終端。", "success")
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
            display_name = user.nickname if user.nickname else "創辦人" if user.email.lower().strip() == ADMIN_EMAIL.lower().strip() else "投資專家"
            flash(f"✅ 歡迎回來，{display_name}！戰情系統已成功解鎖。", "success")
            return redirect(url_for('index'))
        flash("❌ Email 或密碼錯誤。", "danger")
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ==========================================
# 🎯 方案常數：集中管理所有定價 (全新三階段配置)
# ==========================================
class PlanConfig:
    """銷售方案定價配置"""
    PRO_MONTHLY = {
        'name': '專業版月付',
        'amount': 299,
        'item_name': 'Roger 量化戰情室 Pro 月付方案',
        'trade_desc': 'Roger SaaS Pro 月度訂閱'
    }
    PRO_YEARLY = {
        'name': '專業版年付',
        'amount': 2888,
        'item_name': 'Roger 量化戰情室 Pro 年付方案',
        'trade_desc': 'Roger SaaS Pro 年度訂閱（享優惠）'
    }
    PRO_LIFETIME = {
        'name': '終身版',
        'amount': 8888,
        'item_name': 'Roger 量化戰情室 Pro 終身授權',
        'trade_desc': 'Roger SaaS Pro 終身買斷'
    }

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

    # 取得用戶選擇的方案
    plan_type = request.form.get('plan', 'pro_lifetime').strip()
    
    # 根據方案選擇對應設定
    if plan_type == 'pro_monthly':
        plan = PlanConfig.PRO_MONTHLY
    elif plan_type == 'pro_yearly':
        plan = PlanConfig.PRO_YEARLY
    else:
        plan = PlanConfig.PRO_LIFETIME

    trade_no = "RG" + datetime.now().strftime("%Y%m%d%H%M%S") + "".join(random.choices(string.ascii_uppercase, k=2))
    
    new_order = Order(
        user_id=current_user.id, 
        merchant_trade_no=trade_no, 
        amount=plan['amount']
    )
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
        'TotalAmount': plan['amount'],
        'TradeDesc': plan['trade_desc'],
        'ItemName': plan['item_name'],
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
                
                # 根據訂單金額判斷方案類型
                if order.amount == PlanConfig.PRO_LIFETIME['amount']:
                    # 終身版：永久 VIP
                    user.is_vip = True
                    user.vip_since = datetime.now()
                    user.vip_expires_at = None
                    user.canceled_at = None
                    logger.info(f"💎 終身版付款成功！會員 {user.email} 已解鎖永久 Pro 權限")
                else:
                    # 月付/年付：設定 VIP 和到期日
                    user.is_vip = True
                    user.vip_since = datetime.now()
                    user.canceled_at = None
                    
                    # 計算到期日
                    if order.amount == PlanConfig.PRO_YEARLY['amount']:
                        user.vip_expires_at = datetime.now() + timedelta(days=365)
                        logger.info(f"💳 年付方案付款成功！會員 {user.email} 訂閱至 {user.vip_expires_at.strftime('%Y-%m-%d')}")
                    else:
                        user.vip_expires_at = datetime.now() + timedelta(days=30)
                        logger.info(f"💳 月付方案付款成功！會員 {user.email} 訂閱至 {user.vip_expires_at.strftime('%Y-%m-%d')}")
                    
                db.session.commit()
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
    
    # 🚀 升級精算引擎：遍歷全域 VIP 準確統計各級距生態分佈
    all_vips = User.query.filter_by(is_vip=True).all()
    lifetime_count = 0
    yearly_count = 0
    monthly_count = 0
    
    for u in all_vips:
        # 排除創辦人自身帳號干擾數據真實度
        if u.email.lower().strip() == ADMIN_EMAIL.lower().strip():
            continue
            
        if u.vip_since and not u.vip_expires_at:
            lifetime_count += 1
        elif u.vip_since and u.vip_expires_at:
            days_diff = (u.vip_expires_at - u.vip_since).days
            if days_diff > 300:
                yearly_count += 1
            else:
                monthly_count += 1
    
    paid_orders = Order.query.filter_by(status='paid').all()
    total_gmv = sum(o.amount for o in paid_orders)
    
    # 提升載入筆數以利查帳與搜尋覆蓋率
    users = User.query.order_by(User.created_at.desc()).limit(100).all()
    orders = Order.query.order_by(Order.created_at.desc()).limit(100).all()
    
    return render_template(
        'admin.html', 
        total_users=total_users, 
        vip_users=vip_users, 
        lifetime_count=lifetime_count,
        yearly_count=yearly_count,
        monthly_count=monthly_count,
        total_gmv=total_gmv, 
        users=users, 
        orders=orders
    )

# 🚀 升級新增：安全直連維修通道 - 透過總管登入自動向 Aiven 擴充 nickname 欄位
@app.route('/admin/system/db_upgrade')
@login_required
@admin_required
def admin_system_db_upgrade():
    try:
        db.session.execute(text("ALTER TABLE users ADD COLUMN nickname VARCHAR(100);"))
        db.session.commit()
        flash("🛠️ 雲端沙盒遷移成功！Aiven 資料庫已完美擴充 nickname 屬性欄位。", "success")
    except Exception as e:
        db.session.rollback()
        # 若報錯代表欄位很可能已經存在，為正常現象
        flash(f"ℹ️ 資料庫同步狀態檢測：欄位已就緒或遇到提醒 ({str(e)})", "info")
    return redirect(url_for('admin_dashboard'))

# 🚀 升級重構：三段式精細時長手動發送引擎 (支援送月卡/年卡/終身)
@app.route('/admin/grant_vip/<int:user_id>/<plan_type>', methods=['POST'])
@login_required
@admin_required
def admin_grant_vip(user_id, plan_type):
    target_user = User.query.get_or_404(user_id)
    
    if target_user.email.lower().strip() == ADMIN_EMAIL.lower().strip():
        flash("⚠️ 創辦人防護覆寫：總管核心權限具有系統頂層豁免，無需進行手動時效派發。", "warning")
        return redirect(url_for('admin_dashboard'))
        
    target_user.is_vip = True
    target_user.vip_since = datetime.now()
    target_user.canceled_at = None
    
    if plan_type == 'monthly':
        target_user.vip_expires_at = datetime.now() + timedelta(days=30)
        action_text = "Pro 月費授權 (效期 30 天)"
    elif plan_type == 'yearly':
        target_user.vip_expires_at = datetime.now() + timedelta(days=365)
        action_text = "Pro 年費旗艦 (效期 365 天)"
    else:
        target_user.vip_expires_at = None # 終身無限期
        action_text = "Pro 終身買斷通行證"
        
    db.session.commit()
    logger.info(f"🎁 中台精準授權：已為用戶 {target_user.email} 開通 {action_text}")
    flash(f"🎁 成功為帳號 {target_user.email} 派發 {action_text}！", "success")
    return redirect(url_for('admin_dashboard'))

# 🚀 保留強制降級中斷權限功能
@app.route('/admin/revoke_vip/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def admin_revoke_vip(user_id):
    target_user = User.query.get_or_404(user_id)
    if target_user.email.lower().strip() == ADMIN_EMAIL.lower().strip():
        flash("⛔ 致命攔截：無法撤銷系統創辦人的主控權利。", "danger")
        return redirect(url_for('admin_dashboard'))
        
    target_user.is_vip = False
    target_user.canceled_at = datetime.now()
    db.session.commit()
    flash(f"💥 覆寫生效：已立即終止用戶 {target_user.email} 的 Pro 專屬運算通道。", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_user(user_id):
    target_user = User.query.get_or_404(user_id)
    
    if target_user.email.lower().strip() == ADMIN_EMAIL.lower().strip():
        flash("⛔ 致命攔截：系統嚴禁刪除創辦人總管核心帳號。", "danger")
        return redirect(url_for('admin_dashboard'))
        
    deleted_email = target_user.email
    db.session.delete(target_user)
    db.session.commit()
    
    logger.warning(f"💥 總管執行核爆指令：已徹底抹除會員 {deleted_email} 及其連動數據。")
    flash(f"💥 已將帳號 {deleted_email} 從系統資料庫徹底銷毀！", "success")
    return redirect(url_for('admin_dashboard'))

# ==========================================
# 🎯 路由設計：戰情功能 (Freemium 權限防護版)
# ==========================================
@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

# 🚀 鎖定：僅 VIP 或是創辦人解鎖個股獨立深度通道與 AI 分析
@app.route('/analyze', methods=['POST'])
@login_required
@vip_required
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

# 🚀 開放：總經戰情室作為免費導流端，登入即可存取
@app.route('/analyze')
@login_required
def analyzes():
    return render_template('analyze.html')

# 🚀 鎖定：量化動態回測僅限 Pro 或創辦人使用
@app.route('/backtest')
@login_required
@vip_required
def backtest_page():
    return render_template('backtest.html')

# 🚀 鎖定防護
@app.route('/api/run_backtest', methods=['POST'])
@login_required
@vip_required
def api_run_backtest():
    data = request.get_json() or {}
    ticker = data.get('ticker', '2330.TW')
    start_date = data.get('start_date', '2000-01-01')
    end_date = data.get('end_date', datetime.now().strftime('%Y-%m-%d'))
    result = backtest_engine.run_backtest_json(ticker=ticker, start_date=start_date, end_date=end_date)
    return jsonify(result), 200


if __name__ == "__main__":  
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))