# ==========================================
# 自選股路由
# ==========================================
import logging
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash
from flask_login import login_required, current_user
from app import db
from app.models import WatchlistItem
import stock_PE

logger = logging.getLogger(__name__)

watchlist_bp = Blueprint('watchlist', __name__)


@watchlist_bp.route('/watchlist', methods=['GET'])
@login_required
def watchlist_dashboard():
    """顯示自選股儀表板"""
    items = WatchlistItem.query.filter_by(user_id=current_user.id).order_by(
        WatchlistItem.created_at.desc()
    ).all()
    
    # 取得每隻股票的 PE 數據
    enriched_items = []
    for item in items:
        pe_data = {}
        try:
            pe_data = stock_PE.get_pe_data(item.stock_code) or {}
        except Exception as e:
            logger.warning(f"取得 {item.stock_code} PE 數據失敗: {str(e)}")
        
        enriched_items.append({
            'id': item.id,
            'stock_code': item.stock_code,
            'stock_name': item.stock_name or item.stock_code,
            'pe_ratio': pe_data.get('pe_ratio', None),
            'pe_grade': pe_data.get('grade', 'N/A'),
            'ai_insight': pe_data.get('insight', ''),
            'created_at': item.created_at,
        })
    
    return render_template('watchlist.html', items=enriched_items)


@watchlist_bp.route('/watchlist/add', methods=['POST'])
@login_required
def add_watchlist():
    """新增股票至自選股"""
    stock_code = request.form.get('stock_code', '').strip()
    
    if not stock_code:
        flash('請輸入股票代碼', 'danger')
        return redirect(url_for('watchlist.watchlist_dashboard'))
    
    # 檢查是否已存在
    existing = WatchlistItem.query.filter_by(
        user_id=current_user.id,
        stock_code=stock_code
    ).first()
    
    if existing:
        flash(f'{stock_code} 已在自選股中', 'warning')
        return redirect(url_for('watchlist.watchlist_dashboard'))
    
    # 嘗試取得股票名稱
    stock_name = ''
    try:
        df = stock_PE.get_stock_data(stock_code)
        if df is not None and not df.empty:
            stock_name = str(df.iloc[0].get('name', '')) if 'name' in df.columns else ''
    except Exception:
        pass
    
    item = WatchlistItem(
        user_id=current_user.id,
        stock_code=stock_code,
        stock_name=stock_name
    )
    db.session.add(item)
    db.session.commit()
    
    flash(f'✅ {stock_code} 已加入自選股', 'success')
    return redirect(url_for('watchlist.watchlist_dashboard'))


@watchlist_bp.route('/watchlist/remove/<int:item_id>', methods=['POST'])
@login_required
def remove_watchlist(item_id):
    """從自選股移除股票"""
    item = WatchlistItem.query.filter_by(
        id=item_id,
        user_id=current_user.id
    ).first_or_404()
    
    db.session.delete(item)
    db.session.commit()
    
    flash(f'🗑️ {item.stock_code} 已從自選股移除', 'info')
    return redirect(url_for('watchlist.watchlist_dashboard'))


@watchlist_bp.route('/api/watchlist/pe', methods=['GET'])
@login_required
def api_watchlist_pe():
    """
    API 端點：取得自選股股票的 PE 比率
    
    Returns:
        JSON: 包含每隻股票的 PE 數據
    """
    items = WatchlistItem.query.filter_by(user_id=current_user.id).all()
    
    result = []
    for item in items:
        pe_data = {}
        try:
            pe_data = stock_PE.get_pe_data(item.stock_code) or {}
        except Exception as e:
            logger.warning(f"取得 {item.stock_code} PE 數據失敗: {str(e)}")
        
        result.append({
            'id': item.id,
            'stock_code': item.stock_code,
            'stock_name': item.stock_name or item.stock_code,
            'pe_ratio': pe_data.get('pe_ratio', None),
            'pe_grade': pe_data.get('grade', 'N/A'),
            'ai_insight': pe_data.get('insight', ''),
        })
    
    return jsonify(result)
