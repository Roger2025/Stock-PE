# ==========================================
# 自選股路由
# ==========================================
import logging
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash
from flask_login import login_required, current_user
from app import db
from app.models import WatchlistItem
import stock_PE
import json
import pandas as pd
from datetime import datetime

logger = logging.getLogger(__name__)

watchlist_bp = Blueprint('watchlist', __name__)


@watchlist_bp.route('/watchlist', methods=['GET'])
@login_required
def watchlist_dashboard():
    """顯示自選股儀表板"""
    items = WatchlistItem.query.filter_by(user_id=current_user.id).order_by(
        WatchlistItem.order_index.asc()
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
            'valuation': pe_data.get('valuation', ''),
            'ai_insight': pe_data.get('insight', ''),
            'zones': pe_data.get('zones', {}),
            'zone_distribution': pe_data.get('zone_distribution', {}),
            'historical_avg': pe_data.get('historical_avg', None),
            'created_at': item.created_at,
        })
    
    return render_template('watchlist.html', items=enriched_items)


@watchlist_bp.route('/watchlist/<stock_code>', methods=['GET'])
@login_required
def watchlist_detail(stock_code):
    """顯示單隻股票的詳細河流圖"""
    # 檢查是否在自選股中
    item = WatchlistItem.query.filter_by(
        user_id=current_user.id,
        stock_code=stock_code
    ).first_or_404()
    
    # 取得 PE 數據
    pe_data = {}
    try:
        pe_data = stock_PE.get_pe_data(stock_code) or {}
    except Exception as e:
        logger.warning(f"取得 {stock_code} PE 數據失敗: {str(e)}")
    
    # 取得歷史數據用於河流圖
    df = stock_PE.get_stock_data(stock_code)
    
    dates = []
    pe_values = []
    
    if df is not None and not df.empty:
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df = df.dropna(subset=['date'])
        df = df[df['date'].dt.year <= datetime.now().year]
        df['pe_ratio'] = pd.to_numeric(df['pe_ratio'], errors='coerce')
        df = df.dropna(subset=['pe_ratio'])
        
        dates = df['date'].dt.strftime('%Y-%m-%d').tolist()
        pe_values = df['pe_ratio'].tolist()
    
    return render_template('watchlist_detail.html', 
                         stock=item,
                         pe_data=pe_data,
                         dates=dates,
                         pe_values=pe_values)


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
        if df is not None and not df.empty and 'stock_name' in df.columns:
            # 取得最新一筆的股票名稱
            stock_name = str(df.iloc[-1]['stock_name'])
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


@watchlist_bp.route('/watchlist/reorder', methods=['POST'])
@login_required
def reorder_watchlist():
    """更新自選股排序"""
    try:
        data = request.get_json()
        stock_codes = data.get('stock_codes', [])
        
        if not stock_codes:
            return jsonify({'success': False, 'error': '無效的排序'}), 400
        
        # 更新每隻股票的 order_index
        for index, stock_code in enumerate(stock_codes):
            item = WatchlistItem.query.filter_by(
                user_id=current_user.id,
                stock_code=stock_code
            ).first()
            
            if item:
                item.order_index = index
        
        db.session.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


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
