# ==========================================
# 分析路由（PE 分析/回測）
# ==========================================
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash, session
from flask_login import login_required, current_user

from app.services.ai_report import generate_ai_report
from app.decorators import vip_required
import stock_PE
import backtest_engine

analysis_bp = Blueprint('analysis', __name__)


@analysis_bp.route('/analyze', methods=['POST'])
@vip_required
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
@vip_required
def backtest_page():
    """回測頁面（VIP 功能）"""
    return render_template('backtest.html')


@analysis_bp.route('/api/run_backtest', methods=['POST'])
@vip_required
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


@analysis_bp.route('/backtest_dca')
@login_required
def backtest_dca_page():
    """定額投資回測頁面（VIP 功能）"""
    # 從 session 中取得之前計算的結果
    backtest_result = session.get('dca_backtest_result')
    return render_template('backtest_dca.html', backtest_result=backtest_result)


@analysis_bp.route('/api/run_dca_backtest', methods=['POST'])
@vip_required
def api_run_dca_backtest():
    """執行定額投資回測 API (支援三種策略)"""
    from datetime import datetime
    from flask import session
    data = request.get_json() or {}
    ticker = data.get('ticker', '').strip()
    stock_name = data.get('stock_name', '').strip()
    strategy = data.get('strategy', 'dca')  # 'dca', 'pe', or 'accumulate'
    start_date = data.get('start_date', '2020-01-01')
    end_date = data.get('end_date', datetime.now().strftime('%Y-%m-%d'))
    initial_amount = float(data.get('initial_amount', 10000))
    monthly_amount = float(data.get('monthly_amount', 5000))
    invest_on_pe = data.get('invest_on_pe_threshold')
    
    # 如果沒有股票代號但有名稱，嘗試從名稱推斷（預設使用 2330 台積電）
    if not ticker and stock_name:
        # 簡單映射常見股票名稱
        name_to_code = {
            '台積電': '2330',
            '聯詠': '9871',
            '創見': '2412',
            '宏碁': '2303',
            '華碩': '2338',
            '鴻海': '2317',
            '卜蜂': '1215',
        }
        ticker = name_to_code.get(stock_name, stock_name)
    
    if not ticker:
        return jsonify({'status': 'error', 'message': '請填寫股票名稱或股票代號'}), 400
    
    # 轉換為 yfinance 格式
    ticker_yf = f"{ticker}.TW" if not ticker.endswith('.TW') else ticker
    
    # 根據策略類型執行不同的回測
    if strategy == 'accumulate':
        # PE 择時累積策略 - 必須輸入 PE 門檻值
        if not invest_on_pe:
            return jsonify({'status': 'error', 'message': 'PE 擇時累積策略必須設定 PE 門檻值'}), 400
        result = backtest_engine.run_pe_accumulate_backtest(
            ticker=ticker_yf,
            start_date=start_date,
            end_date=end_date,
            monthly_accumulate=monthly_amount,
            invest_on_pe_threshold=float(invest_on_pe)
        )
    else:
        # 一般 DCA 或 PE 策略
        result = backtest_engine.run_dca_backtest(
            ticker=ticker_yf,
            start_date=start_date,
            end_date=end_date,
            initial_amount=initial_amount,
            monthly_amount=monthly_amount,
            invest_on_pe_threshold=float(invest_on_pe) if invest_on_pe else None
        )
    
    # 加入策略資訊到結果中
    result['strategy'] = strategy
    if stock_name:
        result['stock_name'] = stock_name
    result['ticker'] = ticker
    
    # 儲存結果到 session，這樣切換頁面就不會失去
    session['dca_backtest_result'] = result
    
    return jsonify(result), 200


@analysis_bp.route('/api/get_dca_backtest_result')
@vip_required
def api_get_dca_backtest_result():
    """從 session 取得之前計算的回測結果"""
    from flask import session
    result = session.get('dca_backtest_result')
    if result:
        return jsonify(result), 200
    else:
        return jsonify({'status': 'error', 'message': '尚無回測結果'}), 404
