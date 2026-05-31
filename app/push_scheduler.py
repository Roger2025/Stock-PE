# ==========================================
# APScheduler 每日郵件排程
# ==========================================
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from flask import current_app
from app.email_service import send_watchlist_digest
from app.models import User, WatchlistItem
import stock_PE

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def _send_daily_digest_job():
    """
    每日發送自選股日報給所有 VIP 使用者
    
    執行時間：每天上午 8:00
    """
    logger.info("📧 開始執行每日自選股日報排程...")
    
    try:
        # 取得所有 VIP 使用者
        vip_users = User.query.filter_by(is_vip=True).all()
        
        if not vip_users:
            logger.info("沒有 VIP 使用者，跳過日報發送")
            return
        
        sent_count = 0
        
        for user in vip_users:
            # 取得使用者的自選股
            watchlist = WatchlistItem.query.filter_by(user_id=user.id).all()
            
            if not watchlist:
                logger.info(f"使用者 {user.email} 沒有自選股，跳過")
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
                    logger.warning(f"取得 {item.stock_code} PE 數據失敗: {str(e)}")
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
                        logger.info(f"✅ 日報已發送給 {user.email}")
                    else:
                        logger.warning(f"❌ 日報發送失敗給 {user.email}")
                except Exception as e:
                    logger.error(f"❌ 發送日報時發生錯誤給 {user.email}: {str(e)}")
        
        logger.info(f"📧 每日日報發送完成，共發送 {sent_count}/{len(vip_users)} 封")
        
    except Exception as e:
        logger.error(f"❌ 每日日報排程執行失敗: {str(e)}")


def start_scheduler():
    """啟動排程器"""
    if not scheduler.running:
        # 每天中午 12:50 執行（測試用）
        scheduler.add_job(
            func=_send_daily_digest_job,
            trigger='cron',
            hour=12,
            minute=50,
            id='daily_digest',
            name='每日自選股日報',
            replace_existing=True
        )
        scheduler.start()
        logger.info("📧 每日日報排程器已啟動（測試時間：每天 12:50）")


def shutdown_scheduler():
    """關閉排程器"""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("📧 每日日報排程器已關閉")
