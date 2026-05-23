# ==========================================
# 金流路由（定價/付款/回調）
# ==========================================
import os
import random
import string
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

import ecpay_payment_sdk
from config import Config
from app.models import Order, User
from app import db

payment_bp = Blueprint('payment', __name__)


# ==========================================
# 方案常數
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


@payment_bp.route('/pricing')
@login_required
def pricing():
    return render_template('pricing.html')


@payment_bp.route('/checkout', methods=['POST'])
@login_required
def checkout():
    # 取得用戶選擇的方案
    plan_type = request.form.get('plan', 'pro_lifetime').strip()
    
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
        MerchantID=Config.ECPAY_MERCHANT_ID,
        HashKey=Config.ECPAY_HASH_KEY,
        HashIV=Config.ECPAY_HASH_IV
    )
    
    order_params = {
        'MerchantTradeNo': trade_no,
        'MerchantTradeDate': datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
        'PaymentType': 'aio',
        'TotalAmount': plan['amount'],
        'TradeDesc': plan['trade_desc'],
        'ItemName': plan['item_name'],
        'ReturnURL': f"{Config.BASE_URL}/ecpay_callback",
        'OrderResultURL': f"{Config.BASE_URL}/payment_result",
        'ChoosePayment': 'ALL',
        'EncryptType': 1,
    }
    
    try:
        final_order_params = ecpay_sdk.create_order(order_params)
        action_url = "https://payment-stage.ecpay.com.tw/Cashier/AioCheckOut/V5"
        auto_submit_html = ecpay_sdk.gen_html_post_form(action_url, final_order_params)
        return auto_submit_html
    except Exception as e:
        return "金流系統連接異常，請檢查伺服器日誌。", 500


@payment_bp.route('/ecpay_callback', methods=['GET', 'POST'])
def ecpay_callback():
    # 同時支持 GET 和 POST，測試環境用 GET，正式環境用 POST
    data = request.form.to_dict() if request.method == 'POST' else request.args.to_dict()
    ecpay_sdk = ecpay_payment_sdk.ECPayPaymentSdk(
        MerchantID=Config.ECPAY_MERCHANT_ID,
        HashKey=Config.ECPAY_HASH_KEY,
        HashIV=Config.ECPAY_HASH_IV
    )
    
    if not data.get('CheckMacValue'):
        return '0|Error', 400
    
    if ecpay_sdk.generate_check_mac_value(data) == data.get('CheckMacValue'):
        # DEBUG: 記錄回調數據
        print(f"[PAYMENT DEBUG] RtnCode={data.get('RtnCode')}, MerchantTradeNo={data.get('MerchantTradeNo')}")
        print(f"[PAYMENT DEBUG] All data keys: {list(data.keys())}")
        
        if data.get('RtnCode') == '1':
            trade_no = data.get('MerchantTradeNo')
            order = Order.query.filter_by(merchant_trade_no=trade_no).first()
            
            print(f"[PAYMENT DEBUG] Order found: {order}, status: {order.status if order else 'N/A'}")
            
            if order and order.status == 'pending':
                order.status = 'paid'
                user = User.query.get(order.user_id)
                
                print(f"[PAYMENT DEBUG] Upgrading user {user.id} to VIP")
                
                # 根據訂單金額判斷方案類型
                if order.amount == PlanConfig.PRO_LIFETIME['amount']:
                    # 終身版：永久 VIP
                    user.is_vip = True
                    user.vip_since = datetime.now()
                    user.vip_expires_at = None
                    user.canceled_at = None
                else:
                    # 月付/年付：設定到期日
                    user.is_vip = True
                    user.vip_since = datetime.now()
                    user.canceled_at = None
                    
                    if order.amount == PlanConfig.PRO_YEARLY['amount']:
                        user.vip_expires_at = datetime.now() + timedelta(days=365)
                    else:
                        user.vip_expires_at = datetime.now() + timedelta(days=30)
                
                db.session.commit()
                print(f"[PAYMENT DEBUG] User VIP status updated: is_vip={user.is_vip}, vip_since={user.vip_since}")
            elif order:
                print(f"[PAYMENT DEBUG] Order already paid, skipping")
        else:
            print(f"[PAYMENT DEBUG] RtnCode is not 1, value: {data.get('RtnCode')}")
    
    return '1|OK'
    
    return '0|Error'


@payment_bp.route('/payment_result', methods=['GET', 'POST'])
@login_required
def payment_result():
    # 開發環境：如果 ECPay 沒有 callback，這裡手動升級訂單
    # 正式環境請註解這段
    from flask import current_app
    
    if current_app.debug:  # 只在開發環境啟用
        # 查找用戶最近的 pending 訂單
        pending_order = Order.query.filter_by(
            user_id=current_user.id,
            status='pending'
        ).order_by(Order.created_at.desc()).first()
        
        if pending_order:
            pending_order.status = 'paid'
            user = User.query.get(pending_order.user_id)
            
            # 根據訂單金額判斷方案類型
            if pending_order.amount == PlanConfig.PRO_LIFETIME['amount']:
                user.is_vip = True
                user.vip_since = datetime.now()
                user.vip_expires_at = None
                user.canceled_at = None
            else:
                user.is_vip = True
                user.vip_since = datetime.now()
                user.canceled_at = None
                
                if pending_order.amount == PlanConfig.PRO_YEARLY['amount']:
                    user.vip_expires_at = datetime.now() + timedelta(days=365)
                else:
                    user.vip_expires_at = datetime.now() + timedelta(days=30)
            
            db.session.commit()
            print(f"[DEV MODE] 手動升級用戶 {user.id} VIP 狀態")
    
    flash("🎉 綠界付款流程完成！系統正透過專屬加密通道同步升級您的帳號，請稍候刷新頁面。", "success")
    return redirect(url_for('main.index'))
