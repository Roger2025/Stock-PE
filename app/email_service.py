# ==========================================
# Mailgun Email Service
# ==========================================
import logging
import requests
from datetime import datetime
from flask import current_app, render_template
from app import db
from app.models import EmailLog, User, WatchlistItem

logger = logging.getLogger(__name__)


def _send_mailgun_email(recipient: str, subject: str, html_body: str, email_type: str = 'generic') -> bool:
    """
    通用 Mailgun 發送函數
    
    Args:
        recipient: 收件人電子郵件
        subject: 郵件主旨
        html_body: HTML 郵件內容
        email_type: 郵件類型（用於記錄）
    
    Returns:
        bool: 發送成功與否
    """
    api_key = current_app.config.get('MAILGUN_API_KEY', '')
    mailgun_domain = current_app.config.get('MAILGUN_DOMAIN', '')
    
    if not api_key or not mailgun_domain:
        logger.warning("Mailgun 未配置，跳過發送郵件")
        return False
    
    try:
        response = requests.post(
            f"https://api.mailgun.net/v3/{mailgun_domain}/messages",
            auth=("api", api_key),
            data={
                "from": f"Roger Quant <noreply@{mailgun_domain}>",
                "to": [recipient],
                "subject": subject,
                "html": html_body,
            },
            timeout=15
        )
        
        if response.status_code == 200:
            logger.info(f"✅ 郵件發送成功至 {recipient} ({email_type})")
            return True
        else:
            logger.error(f"❌ 郵件發送失敗至 {recipient}: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"❌ 郵件發送異常至 {recipient}: {str(e)}")
        return False


def _log_email(user_id: int, email_type: str, recipient: str, subject: str, status: str = 'sent'):
    """記錄郵件發送日誌"""
    try:
        email_log = EmailLog(
            user_id=user_id,
            email_type=email_type,
            recipient=recipient,
            subject=subject,
            status=status
        )
        db.session.add(email_log)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"郵件日誌記錄失敗: {str(e)}")


def send_welcome_email(user_email: str, user_nickname: str) -> bool:
    """
    發送歡迎郵件
    
    Args:
        user_email: 使用者電子郵件
        user_nickname: 使用者暱稱
    
    Returns:
        bool: 發送成功與否
    """
    subject = "🎉 歡迎加入 Roger Quant - 您的投資智能戰情室已就緒"
    
    html_body = render_template('email_templates/welcome.html', nickname=user_nickname)
    
    success = _send_mailgun_email(user_email, subject, html_body, email_type='welcome')
    
    # 查找使用者 ID（如果存在）
    user = User.query.filter_by(email=user_email).first()
    if user:
        _log_email(user.id, 'welcome', user_email, subject, 'sent' if success else 'failed')
    
    return success


def send_pe_alert(user_email: str, stock_code: str, stock_name: str, 
                  pe_ratio: float, ai_insight: str) -> bool:
    """
    發送 PE 警示郵件
    
    Args:
        user_email: 使用者電子郵件
        stock_code: 股票代碼
        stock_name: 股票名稱
        pe_ratio: PE 比率
        ai_insight: AI 洞察
    
    Returns:
        bool: 發送成功與否
    """
    # 計算 PE 等級
    if pe_ratio < 10:
        grade = 'A'
        grade_label = '極度低估'
    elif pe_ratio < 15:
        grade = 'B'
        grade_label = '低估'
    elif pe_ratio < 20:
        grade = 'C'
        grade_label = '合理'
    elif pe_ratio < 25:
        grade = 'D'
        grade_label = '高估'
    else:
        grade = 'E'
        grade_label = '極度高估'
    
    subject = f"📊 PE 警示：{stock_code} {stock_name} PE={pe_ratio:.2f} ({grade}級)"
    
    html_body = render_template('email_templates/pe_alert.html',
                                stock_code=stock_code,
                                stock_name=stock_name,
                                pe_ratio=pe_ratio,
                                grade=grade,
                                grade_label=grade_label,
                                ai_insight=ai_insight)
    
    success = _send_mailgun_email(user_email, subject, html_body, email_type='pe_alert')
    
    user = User.query.filter_by(email=user_email).first()
    if user:
        _log_email(user.id, 'pe_alert', user_email, subject, 'sent' if success else 'failed')
    
    return success


def send_backtest_alert(user_email: str, stock_code: str, strategy_name: str,
                        win_rate: float, profit_rate: float) -> bool:
    """
    發送回測警示郵件
    
    Args:
        user_email: 使用者電子郵件
        stock_code: 股票代碼
        strategy_name: 策略名稱
        win_rate: 勝率
        profit_rate: 獲利率
    
    Returns:
        bool: 發送成功與否
    """
    subject = f"📈 回測結果：{stock_code} {strategy_name} - 勝率 {win_rate:.1f}%"
    
    html_body = render_template('email_templates/backtest_alert.html',
                                stock_code=stock_code,
                                strategy_name=strategy_name,
                                win_rate=win_rate,
                                profit_rate=profit_rate)
    
    success = _send_mailgun_email(user_email, subject, html_body, email_type='backtest_alert')
    
    user = User.query.filter_by(email=user_email).first()
    if user:
        _log_email(user.id, 'backtest_alert', user_email, subject, 'sent' if success else 'failed')
    
    return success


def send_watchlist_digest(user_id: int, user_email: str, items: list) -> bool:
    """
    發送自選股日報
    
    Args:
        user_id: 使用者 ID
        user_email: 使用者電子郵件
        items: 自選股項目列表（包含 stock_code, stock_name, pe_ratio 等）
    
    Returns:
        bool: 發送成功與否
    """
    subject = f"📋 Roger Quant 自選股日報 - {datetime.now().strftime('%Y/%m/%d')}"
    
    html_body = render_template('email_templates/watchlist_digest.html',
                                items=items,
                                now=datetime.now())
    
    success = _send_mailgun_email(user_email, subject, html_body, email_type='watchlist_digest')
    
    _log_email(user_id, 'watchlist_digest', user_email, subject, 'sent' if success else 'failed')
    
    return success
