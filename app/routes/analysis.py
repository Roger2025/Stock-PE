# ==========================================
# 分析路由（PE 分析/回測）
# ==========================================
from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from flask_login import login_required, current_user

from app.services.ai_report import generate_ai_report
import stock_PE
import backtest_engine

analysis_bp = Blueprint('analysis', __name__)


@analysis_bp.route('/analyze', methods=['POST'])
@login_required
def analyze():
    """執行個股分析（VIP 功能）"""
    stock_id = request.form.get('stock_id', '').strip()
    if not stock_id:
        return "❌ 請輸入代號", 400
    
    try:
        chart_json_data = stock_PE.get_echarts_data(stock_id)
        df = stock_PE.get_stock_data(stock_id)
        ai_html_report = generate_ai_report(stock_id, df)
        return render_template('result.html', stock_id=stock_id, chart_data=chart_json_data, ai_report=ai_html_report)
    except Exception as e:
        return f"❌ 處理失敗: {str(e)}", 500


@analysis_bp.route('/analyze')
@login_required
def analyzes():
    """分析頁面（GET）"""
    return render_template('analyze.html')


@analysis_bp.route('/backtest')
@login_required
def backtest_page():
    """回測頁面（VIP 功能）"""
    return render_template('backtest.html')


@analysis_bp.route('/api/run_backtest', methods=['POST'])
@login_required
def api_run_backtest():
    """執行回測 API"""
    from datetime import datetime
    data = request.get_json() or {}
    ticker = data.get('ticker', '2330.TW')
    start_date = data.get('start_date', '2000-01-01')
    end_date = data.get('end_date', datetime.now().strftime('%Y-%m-%d'))
    
    result = backtest_engine.run_backtest_json(
        ticker=ticker,
        start_date=start_date,
        end_date=end_date
    )
    return jsonify(result), 200
