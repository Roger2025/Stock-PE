# ==========================================
# 權限裝飾器
# ==========================================
from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user


def admin_required(f):
    """管理員權限裝飾器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("⛔ 需要登入才能進入管理後台。", "danger")
            return redirect(url_for('auth.login'))
        
        from config import Config
        admin_email = Config.ADMIN_EMAIL
        
        if current_user.email.lower().strip() != admin_email.lower().strip():
            flash("⛔ 越權存取攔截：您不具備總管中台的存取權限。", "danger")
            return redirect(url_for('main.index'))
        
        return f(*args, **kwargs)
    return decorated_function


def vip_required(f):
    """VIP 權限裝飾器（支援創辦人無條件穿透）"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        
        from config import Config
        admin_email = Config.ADMIN_EMAIL
        
        # 創辦人免驗證直接放行
        if current_user.email.lower().strip() == admin_email.lower().strip():
            return f(*args, **kwargs)
        
        if not current_user.is_vip:
            flash("👑 此為 Pro 專屬功能！請先升級方案以解鎖個股深度分析與量化回測引擎。", "warning")
            return redirect(url_for('payment.pricing'))
        
        return f(*args, **kwargs)
    return decorated_function
