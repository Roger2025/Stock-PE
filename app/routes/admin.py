# ==========================================
# 管理後台路由
# ==========================================
from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from sqlalchemy import text

from config import Config
from app.models import User, Order
from app import db

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/admin')
@login_required
def admin_dashboard():
    """管理員儀表板"""
    total_users = User.query.count()
    vip_users = User.query.filter_by(is_vip=True).count()
    
    # 統計各級距 VIP
    all_vips = User.query.filter_by(is_vip=True).all()
    lifetime_count = 0
    yearly_count = 0
    monthly_count = 0
    
    for u in all_vips:
        if u.email.lower().strip() == Config.ADMIN_EMAIL.lower().strip():
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


@admin_bp.route('/admin/system/db_upgrade')
@login_required
def admin_system_db_upgrade():
    """資料庫欄位遷移"""
    try:
        db.session.execute(text("ALTER TABLE users ADD COLUMN nickname VARCHAR(100);"))
        db.session.commit()
        flash("🛠️ 雲端沙盒遷移成功！Aiven 資料庫已完美擴充 nickname 屬性欄位。", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"ℹ️ 資料庫同步狀態檢測：欄位已就緒或遇到提醒 ({str(e)})", "info")
    return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/admin/grant_vip/<int:user_id>/<plan_type>', methods=['POST'])
@login_required
def admin_grant_vip(user_id, plan_type):
    """授予 VIP 權限"""
    target_user = User.query.get_or_404(user_id)
    
    if target_user.email.lower().strip() == Config.ADMIN_EMAIL.lower().strip():
        flash("⚠️ 創辦人防護覆寫：總管核心權限具有系統頂層豁免，無需進行手動時效派發。", "warning")
        return redirect(url_for('admin.admin_dashboard'))
    
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
        target_user.vip_expires_at = None
        action_text = "Pro 終身買斷通行證"
    
    db.session.commit()
    flash(f"🎁 成功為帳號 {target_user.email} 開通 {action_text}！", "success")
    return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/admin/revoke_vip/<int:user_id>', methods=['POST'])
@login_required
def admin_revoke_vip(user_id):
    """撤銷 VIP 權限"""
    target_user = User.query.get_or_404(user_id)
    
    if target_user.email.lower().strip() == Config.ADMIN_EMAIL.lower().strip():
        flash("⛔ 致命攔截：無法撤銷系統創辦人的主控權利。", "danger")
        return redirect(url_for('admin.admin_dashboard'))
    
    target_user.is_vip = False
    target_user.canceled_at = datetime.now()
    db.session.commit()
    flash(f"💥 已立即終止用戶 {target_user.email} 的 Pro 專屬運算通道。", "success")
    return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
def admin_delete_user(user_id):
    """刪除用戶"""
    target_user = User.query.get_or_404(user_id)
    
    if target_user.email.lower().strip() == Config.ADMIN_EMAIL.lower().strip():
        flash("⛔ 致命攔截：系統嚴禁刪除創辦人總管核心帳號。", "danger")
        return redirect(url_for('admin.admin_dashboard'))
    
    deleted_email = target_user.email
    db.session.delete(target_user)
    db.session.commit()
    flash(f"💥 已將帳號 {deleted_email} 從系統資料庫徹底銷毀！", "success")
    return redirect(url_for('admin.admin_dashboard'))
