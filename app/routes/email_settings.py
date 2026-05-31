# ==========================================
# Email 訂閱管理路由
# ==========================================
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models import EmailSubscription, EmailLog, WatchlistItem
from app.email_service import send_watchlist_digest
import stock_PE

email_bp = Blueprint('email', __name__, url_prefix='/email')


@email_bp.route('/settings')
@login_required
def email_settings():
    """郵件設定頁面"""
    # 取得使用者所有訂閱
    subscriptions = EmailSubscription.query.filter_by(user_id=current_user.id).all()
    
    # 取得使用者郵件發送歷史
    email_logs = EmailLog.query.filter_by(user_id=current_user.id).order_by(EmailLog.sent_at.desc()).limit(20).all()
    
    # 取得使用者自選股列表
    watchlist = WatchlistItem.query.filter_by(user_id=current_user.id).all()
    
    return render_template('email_settings.html',
                          subscriptions=subscriptions,
                          email_logs=email_logs,
                          watchlist=watchlist)


@email_bp.route('/subscribe', methods=['POST'])
@login_required
def subscribe():
    """訂閱郵件"""
    subscription_type = request.form.get('subscription_type')
    
    if not subscription_type:
        flash('訂閱類型無效', 'danger')
        return redirect(url_for('email.email_settings'))
    
    # 檢查是否已訂閱
    existing = EmailSubscription.query.filter_by(
        user_id=current_user.id,
        subscription_type=subscription_type,
        is_active=True
    ).first()
    
    if existing:
        flash(f'您已經訂閱了 {get_subscription_name(subscription_type)}', 'warning')
    else:
        new_subscription = EmailSubscription(
            user_id=current_user.id,
            subscription_type=subscription_type
        )
        db.session.add(new_subscription)
        db.session.commit()
        flash(f'✅ 成功訂閱 {get_subscription_name(subscription_type)}', 'success')
    
    return redirect(url_for('email.email_settings'))


@email_bp.route('/unsubscribe', methods=['POST'])
@login_required
def unsubscribe():
    """取消訂閱郵件"""
    subscription_type = request.form.get('subscription_type')
    
    if not subscription_type:
        flash('訂閱類型無效', 'danger')
        return redirect(url_for('email.email_settings'))
    
    subscription = EmailSubscription.query.filter_by(
        user_id=current_user.id,
        subscription_type=subscription_type,
        is_active=True
    ).first()
    
    if subscription:
        subscription.is_active = False
        db.session.commit()
        flash(f'✅ 已取消訂閱 {get_subscription_name(subscription_type)}', 'info')
    else:
        flash('找不到您的訂閱記錄', 'warning')
    
    return redirect(url_for('email.email_settings'))


@email_bp.route('/preview-digest', methods=['POST'])
@login_required
def preview_digest():
    """預覽自選股日報"""
    try:
        # 取得使用者自選股
        watchlist = WatchlistItem.query.filter_by(user_id=current_user.id).all()
        
        if not watchlist:
            return jsonify({'error': '您還沒有加入任何自選股'}), 400
        
        # 為每隻股票取得 PE 數據
        items = []
        for item in watchlist:
            try:
                pe_data = stock_PE.get_pe_data(item.stock_code)
                if pe_data:
                    items.append({
                        'stock_code': item.stock_code,
                        'stock_name': item.stock_name or item.stock_code,
                        'pe_ratio': pe_data.get('pe_ratio', None),
                        'pe_grade': pe_data.get('grade', 'N/A'),
                        'ai_insight': pe_data.get('insight', ''),
                    })
            except Exception as e:
                items.append({
                    'stock_code': item.stock_code,
                    'stock_name': item.stock_name or item.stock_code,
                    'pe_ratio': None,
                    'pe_grade': 'N/A',
                    'ai_insight': f'無法取得數據: {str(e)}',
                })
        
        return jsonify({
            'success': True,
            'items': items,
            'count': len(items)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@email_bp.route('/send-now', methods=['POST'])
@login_required
def send_now():
    """立即發送自選股日報 - 發送到登入者的 Email"""
    try:
        # 取得使用者自選股
        watchlist = WatchlistItem.query.filter_by(user_id=current_user.id).all()
        
        if not watchlist:
            return jsonify({'error': '您還沒有加入任何自選股'}), 400
        
        # 為每隻股票取得 PE 數據
        items = []
        for item in watchlist:
            try:
                pe_data = stock_PE.get_pe_data(item.stock_code)
                if pe_data:
                    items.append({
                        'stock_code': item.stock_code,
                        'stock_name': item.stock_name or item.stock_code,
                        'pe_ratio': pe_data.get('pe_ratio', None),
                        'pe_grade': pe_data.get('grade', 'N/A'),
                        'ai_insight': pe_data.get('insight', ''),
                    })
            except Exception as e:
                items.append({
                    'stock_code': item.stock_code,
                    'stock_name': item.stock_name or item.stock_code,
                    'pe_ratio': None,
                    'pe_grade': 'N/A',
                    'ai_insight': f'無法取得數據: {str(e)}',
                })
        
        # 直接發送到登入者的 Email
        success = send_watchlist_digest(current_user.id, current_user.email, items)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'✅ 日報已發送到 {current_user.email}'
            })
        else:
            return jsonify({
                'success': False,
                'message': '❌ 郵件發送失敗，請稍後再試'
            }), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def get_subscription_name(subscription_type):
    """取得訂閱類型的中文名稱"""
    names = {
        'watchlist_digest': '自選股日報',
        'pe_alert': 'PE 警示通知',
        'backtest_alert': '回測警示通知'
    }
    return names.get(subscription_type, subscription_type)


@email_bp.route('/send-all-now', methods=['POST'])
@login_required
def send_all_now():
    """手動觸發：立即發送日報給所有 VIP 使用者（管理員功能）"""
    try:
        from app.models import User
        
        # 取得所有 VIP 使用者
        vip_users = User.query.filter_by(is_vip=True).all()
        
        if not vip_users:
            return jsonify({'success': False, 'message': '沒有 VIP 使用者'}), 400
        
        sent_count = 0
        failed_count = 0
        
        for user in vip_users:
            # 取得使用者的自選股
            watchlist = WatchlistItem.query.filter_by(user_id=user.id).all()
            
            if not watchlist:
                continue
            
            # 為每隻股票取得 PE 數據
            items = []
            for item in watchlist:
                try:
                    pe_data = stock_PE.get_pe_data(item.stock_code)
                    if pe_data:
                        items.append({
                            'stock_code': item.stock_code,
                            'stock_name': item.stock_name or item.stock_code,
                            'pe_ratio': pe_data.get('pe_ratio', None),
                            'pe_grade': pe_data.get('grade', 'N/A'),
                            'ai_insight': pe_data.get('insight', ''),
                        })
                except Exception as e:
                    items.append({
                        'stock_code': item.stock_code,
                        'stock_name': item.stock_name or item.stock_code,
                        'pe_ratio': None,
                        'pe_grade': 'N/A',
                        'ai_insight': '無法取得數據',
                    })
            
            # 如果有 PE 數據，發送日報
            if items:
                try:
                    success = send_watchlist_digest(user.id, user.email, items)
                    if success:
                        sent_count += 1
                    else:
                        failed_count += 1
                except Exception as e:
                    failed_count += 1
        
        message = f'✅ 已發送 {sent_count} 封'
        if failed_count > 0:
            message += f'，❌ 失敗 {failed_count} 封'
        
        return jsonify({
            'success': True,
            'message': message,
            'sent': sent_count,
            'failed': failed_count
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'錯誤：{str(e)}'}), 500
