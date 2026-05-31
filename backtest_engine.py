import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import os

# 資料來源設定（可切換 yfinance 或 FinMind）
DATA_SOURCE = os.getenv('DATA_SOURCE', 'yfinance').lower()  # 'yfinance' or 'finmind'

def _scalar(x):
    try:
        return x.item()
    except AttributeError:
        return float(x)

def fetch_series(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    獲取股票數據（支援 yfinance 和 FinMind）
    
    Args:
        symbol: 股票代號（如 "2330.TW" 或 "2330"）
        start_date: 開始日期（格式：YYYY-MM-DD）
        end_date: 結束日期（格式：YYYY-MM-DD）
    
    Returns:
        DataFrame: 包含 Close 和 Adj Close 欄位的數據
    """
    if DATA_SOURCE == 'finmind':
        return _fetch_from_finmind(symbol, start_date, end_date)
    else:
        return _fetch_from_yfinance(symbol, start_date, end_date)

def _fetch_from_yfinance(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """從 yfinance 獲取數據"""
    # 抓取原始數據：強制加入 auto_adjust=False，保證真實收盤價與還原價徹底分流
    df = yf.download(symbol, start=start_date, end=end_date, auto_adjust=False, progress=False)
    
    if df is None or df.empty:
        raise ValueError(f"抓不到 {symbol} 在 {start_date} 至 {end_date} 的資料，請檢查代號或日期是否包含交易日。")
        
    # 扁平化 MultiIndex 欄位 (兼容最新版 yfinance)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
        
    # 確認基礎收盤價存在
    if "Close" not in df.columns:
        raise ValueError("下載的數據缺失基礎收盤價 (Close) 欄位。")
        
    # 【終極防彈機制】建立全新乾淨表，保證絕對存在命名的 "Close" 與 "Adj Close" 兩個欄位
    res = pd.DataFrame(index=df.index)
    
    # 嚴格防禦：萬一遇到欄位重複導致取得 DataFrame，強制提取第一行 Series
    close_s = df["Close"].iloc[:, 0] if isinstance(df["Close"], pd.DataFrame) else df["Close"]
    res["Close"] = close_s
    
    if "Adj Close" in df.columns:
        adj_s = df["Adj Close"].iloc[:, 0] if isinstance(df["Adj Close"], pd.DataFrame) else df["Adj Close"]
        res["Adj Close"] = adj_s
    else:
        # 如果底層沒給 Adj Close (代表 Close 預設已被套件還原)，就直接複製 Close 填上
        res["Adj Close"] = close_s
        
    res = res.dropna()
    res.index = res.index.tz_localize(None)
    return res

def _fetch_from_finmind(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """從 FinMind 獲取數據"""
    try:
        from finmind_data import get_stock_from_finmind
        
        # 移除 .TW 後綴
        stock_id = symbol.replace('.TW', '')
        
        df = get_stock_from_finmind(stock_id, start_date, end_date)
        
        if df.empty:
            raise ValueError(f"抓不到 {symbol} 在 {start_date} 至 {end_date} 的 FinMind 資料。")
        
        # 確保有必要的欄位
        res = pd.DataFrame(index=df.index)
        
        if 'Close' in df.columns:
            res['Close'] = df['Close']
        else:
            raise ValueError("FinMind 數據缺失 Close 欄位。")
        
        if 'Adj Close' in df.columns:
            res['Adj Close'] = df['Adj Close']
        else:
            res['Adj Close'] = res['Close']
        
        res = res.dropna()
        return res
    except ImportError:
        print("⚠️ finmind_data.py 模組不存在，自動切換回 yfinance")
        return _fetch_from_yfinance(symbol, start_date, end_date)
    except Exception as e:
        print(f"⚠️ FinMind 獲取數據失敗: {e}，自動切換回 yfinance")
        return _fetch_from_yfinance(symbol, start_date, end_date)

def find_signals(drawdown: pd.Series, thr: float, min_gap: int = 60):
    sigs, last_i = [], -10**9
    vals, idx = drawdown.values, drawdown.index
    for i in range(1, len(drawdown)):
        crossed = (vals[i] <= -thr) and (vals[i-1] > -thr)
        far_enough = (i - last_i) >= min_gap
        if crossed and far_enough:
            sigs.append(idx[i])
            last_i = i
    return sigs

def forward_return(series: pd.Series, start_date: pd.Timestamp, years: int):
    loc0 = series.index.searchsorted(start_date)
    if loc0 >= len(series): return None
    est_end = start_date + pd.DateOffset(years=years)
    loc1 = series.index.searchsorted(est_end)
    if loc1 >= len(series): return None
    s0 = _scalar(series.iloc[loc0])
    s1 = _scalar(series.iloc[loc1])
    return s1 / s0 - 1.0

def run_backtest_json(ticker="2330.TW", start_date="2000-01-01", end_date="2026-05-10", thresholds=[0.1, 0.2, 0.3, 0.4], forward_years=[1, 3], min_gap_days=60):
    try:
        # 取得經過終極防彈機制清洗後的雙欄位 DataFrame
        df_data = fetch_series(ticker, start_date, end_date)
        
        # 絕對不再發生 KeyError
        px_adj = df_data["Adj Close"]
        px_real = df_data["Close"]
        
        peak = px_adj.cummax()
        dd = px_adj / peak - 1.0

        signals = {thr: find_signals(dd, thr, min_gap_days) for thr in thresholds}
        
        # 完整保留你的明細與報酬蒐集邏輯，一字不漏
        detail_rows = []
        ret_map = {ny: {thr: [] for thr in thresholds} for ny in forward_years}
        all_valid_returns = []

        for thr in sorted(thresholds):
            for d0 in signals[thr]:
                for ny in sorted(forward_years):
                    r = forward_return(px_adj, d0, ny)
                    if r is not None:
                        ret_pct = round(_scalar(r) * 100, 2)
                        ret_map[ny][thr].append(ret_pct)
                        all_valid_returns.append(ret_pct)
                        ret_display = ret_pct
                    else:
                        ret_display = "時間未到"
                        
                    detail_rows.append({
                        "threshold": f"-{int(thr*100)}%",
                        "forward_year": ny,
                        "date": d0.strftime('%Y-%m-%d'),
                        "return_pct": ret_display
                    })
        
        detail_rows.sort(key=lambda x: x['date'], reverse=True)

        # 捕捉真實開盤日與起迄價格 (完整打包真實價與還原價給前端)
        actual_start_date = df_data.index[0].strftime('%Y-%m-%d')
        start_p = round(_scalar(px_real.iloc[0]), 2)
        start_p_adj = round(_scalar(px_adj.iloc[0]), 2)
        end_p = round(_scalar(px_real.iloc[-1]), 2)
        curr_p = end_p  
        
        max_dd = round(float(dd.min()) * 100, 2)
        total_signals_count = sum(len(signals[thr]) for thr in thresholds)
        
        if all_valid_returns:
            overall_winrate = round(float(np.mean(np.array(all_valid_returns) > 0)) * 100, 1)
        else:
            overall_winrate = 0.0

        kpi_cards = {
            "actual_start_date": actual_start_date,
            "start_price": start_p,
            "start_price_adj": start_p_adj,
            "end_price": end_p,
            "current_price": curr_p,
            "max_drawdown": max_dd,
            "total_signals": total_signals_count,
            "overall_winrate": overall_winrate
        }

        summary_rows = []
        for thr in sorted(thresholds):
            thr_label = f"-{int(thr*100)}%"
            for ny in sorted(forward_years):
                arr = np.array(ret_map[ny][thr], dtype=float)
                if arr.size == 0:
                    summary_rows.append({
                        "threshold": thr_label,
                        "forward_year": ny,
                        "samples": 0,
                        "mean_ret": "--",
                        "median_ret": "--",
                        "win_rate": "--",
                        "mean_ann": "--"
                    })
                else:
                    mean_r = float(np.mean(arr))
                    median_r = float(np.median(arr))
                    win_r = float(np.mean(arr > 0)) * 100
                    ann_r = ((1.0 + mean_r / 100.0) ** (1.0 / ny) - 1.0) * 100
                    
                    summary_rows.append({
                        "threshold": thr_label,
                        "forward_year": ny,
                        "samples": int(arr.size),
                        "mean_ret": round(mean_r, 2),
                        "median_ret": round(median_r, 2),
                        "win_rate": round(win_r, 1),
                        "mean_ann": round(ann_r, 2)
                    })

        # 【核心同步】：把顯示用的真實價 (prices) 與計算連動用的還原價 (adj_prices) 一起傳給前端
        chart_data = {
            "dates": df_data.index.strftime('%Y-%m-%d').tolist(),
            "prices": [round(_scalar(p), 2) for p in px_real.values],
            "adj_prices": [round(_scalar(p), 2) for p in px_adj.values],
            "drawdowns": [round(_scalar(d) * 100, 2) for d in dd.values],
            "signals": {f"-{int(thr*100)}%": [d.strftime('%Y-%m-%d') for d in signals[thr]] for thr in thresholds}
        }

        return {
            "status": "success",
            "ticker": ticker,
            "start_date": start_date,
            "end_date": end_date,
            "kpi_cards": kpi_cards,
            "summary_table": summary_rows,
            "chart_data": chart_data,
            "details": detail_rows
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def build_pe_cache(ticker: str, start_date: str, end_date: str):
    """
    在回測開始前，一次性獲取所有歷史 PE 數據（不過濾日期）。
    查詢時再過濾目標日期範圍。
    返回 dict: {date_str: pe_ratio}
    """
    pe_cache = {}
    try:
        import stock_PE
        df = stock_PE.get_stock_data(ticker)
        if df is None or df.empty:
            print(f"⚠️ 股票 {ticker} 無 PE 數據")
            return pe_cache
        
        df['date'] = pd.to_datetime(df['date'])
        df['pe_ratio'] = pd.to_numeric(df['pe_ratio'], errors='coerce')
        df = df.dropna(subset=['pe_ratio'])
        
        # 過濾日期範圍
        start_dt = pd.Timestamp(start_date)
        end_dt = pd.Timestamp(end_date)
        df = df[(df['date'] >= start_dt) & (df['date'] <= end_dt)]
        
        if df.empty:
            print(f"⚠️ 股票 {ticker} 在 {start_date} 至 {end_date} 區間無 PE 數據")
            return pe_cache
        
        # 對於每個日期，記錄該日期的 PE 值
        for _, row in df.iterrows():
            pe_cache[row['date'].strftime('%Y-%m-%d')] = row['pe_ratio']
        
        print(f"✅ PE 緩存建立成功 - 股票 {ticker}: {len(pe_cache)} 筆歷史 PE 數據 ({start_date} ~ {end_date})")
    except Exception as e:
        print(f"❌ PE 緩存建立失敗: {e}")
        import traceback
        traceback.print_exc()
    return pe_cache


def get_pe_for_date(pe_cache: dict, target_date: pd.Timestamp) -> float:
    """
    從 PE 緩存中獲取指定日期之前（包含）的最新 PE 值。
    如果找不到，返回 None。
    """
    # 找到目標日期之前（包含）的最新 PE 數據
    past_dates = [d for d, pe in pe_cache.items() if d <= target_date.strftime('%Y-%m-%d')]
    if not past_dates:
        return None
    # 取最新的日期
    latest_date = max(past_dates)
    return pe_cache[latest_date]


def run_dca_backtest(ticker="2330.TW", start_date="2020-01-01", end_date="2026-05-28", 
                     initial_amount=10000, monthly_amount=5000, invest_on_pe_threshold=None):
    """
    定額投資策略回測 (Dollar Cost Averaging Backtest)
    
    Args:
        ticker: 股票代號 (如 "2330.TW")
        start_date: 開始日期
        end_date: 結束日期
        initial_amount: 初始投資金額
        monthly_amount: 每月定額投入金額
        invest_on_pe_threshold: 可選，當 PE < 此值時才投資 (None = 每月固定投資)
    
    Returns:
        dict: 回測結果
    """
    try:
        # 取得股票數據
        df_data = fetch_series(ticker, start_date, end_date)
        px = df_data["Adj Close"]
        
        # 計算日期範圍
        start_dt = pd.Timestamp(start_date)
        end_dt = pd.Timestamp(end_date)
        
        # 【優化】在回測開始前一次性獲取所有歷史 PE 數據
        pe_cache = {}
        if invest_on_pe_threshold:
            pe_cache = build_pe_cache(ticker.replace('.TW', ''), start_date, end_date)
        
        # 生成投資日期列表（每月第一個交易日）
        trading_calendar = px.index
        investment_dates = []
        
        # 取得每月第一個交易日
        monthly_first_days = pd.date_range(start=start_dt, end=end_dt, freq='MS')
        for month_day in monthly_first_days:
            # 找到該月第一個交易日
            first_trading_day = trading_calendar[trading_calendar >= month_day]
            if len(first_trading_day) > 0:
                investment_dates.append(first_trading_day[0])
        
        # 執行回測
        total_invested = 0  # 累計投入金額
        total_shares = 0    # 累計持有股數
        investment_log = []   # 投資記錄
        
        current_shares = 0
        daily_values = []
        
        for i, date in enumerate(px.index):
            # 計算到當日的組合價值
            if current_shares > 0:
                value = current_shares * px.loc[date]
            else:
                value = 0
            
            # 獲取當日 PE（如果有 PE 緩存）
            current_pe = None
            if pe_cache:
                current_pe = get_pe_for_date(pe_cache, date)
            
            daily_values.append({
                'date': date.strftime('%Y-%m-%d'),
                'price': round(float(px.loc[date]), 2),
                'portfolio_value': round(value, 2),
                'pe_ratio': round(current_pe, 2) if current_pe else None
            })
            
            # 檢查是否是投資日
            if date in investment_dates:
                # 檢查 PE 門檻（如果有設定）
                should_invest = True
                pe_status = ""
                current_pe = None
                
                if invest_on_pe_threshold and pe_cache:
                    current_pe = get_pe_for_date(pe_cache, date)
                    if current_pe is not None and current_pe >= invest_on_pe_threshold:
                        should_invest = False
                        pe_status = f"PE={current_pe:.1f} >= {invest_on_pe_threshold}，跳過"
                    elif current_pe is not None:
                        pe_status = f"PE={current_pe:.1f} < {invest_on_pe_threshold}，投資"
                
                # 【修改】記錄所有投資日，包含未投資的
                if should_invest:
                    # 初始投資
                    if total_invested == 0 and i == 0:
                        invest_amount = initial_amount
                    else:
                        invest_amount = monthly_amount
                    
                    # 計算買入股數（取整數股）
                    shares_to_buy = int(invest_amount / px.loc[date])
                    
                    if shares_to_buy > 0:
                        cost = shares_to_buy * px.loc[date]
                        current_shares += shares_to_buy
                        total_invested += cost
                        
                        investment_log.append({
                            'date': date.strftime('%Y-%m-%d'),
                            'price': round(float(px.loc[date]), 2),
                            'amount': round(cost, 2),
                            'shares': shares_to_buy,
                            'total_shares': current_shares,
                            'total_invested': round(total_invested, 2),
                            'pe_ratio': round(current_pe, 2) if current_pe else None,
                            'status': '投資'
                        })
                else:
                    # 記錄未投資的月份
                    investment_log.append({
                        'date': date.strftime('%Y-%m-%d'),
                        'price': round(float(px.loc[date]), 2),
                        'amount': 0,
                        'shares': 0,
                        'total_shares': current_shares,
                        'total_invested': round(total_invested, 2),
                        'pe_ratio': round(current_pe, 2) if current_pe else None,
                        'status': '跳過'
                    })
        
        # 計算最終結果
        final_value = daily_values[-1]['portfolio_value'] if daily_values else 0
        final_price = daily_values[-1]['price'] if daily_values else 0
        total_profit = final_value - total_invested
        total_return_pct = (total_profit / total_invested * 100) if total_invested > 0 else 0
        
        # 計算投資月數
        invest_months = len(investment_log)
        
        # 計算年化報酬率 (CAGR)
        years = (end_dt - start_dt).days / 365.25
        if years > 0 and total_invested > 0:
            cagr = ((final_value / total_invested) ** (1 / years) - 1) * 100 if final_value > total_invested else \
                   -((1 - final_value / total_invested) ** (1 / years)) * 100
        else:
            cagr = 0
        
        # 計算最大回撤
        peak = 0
        max_drawdown = 0
        for dv in daily_values:
            if dv['portfolio_value'] > peak:
                peak = dv['portfolio_value']
            drawdown = (peak - dv['portfolio_value']) / peak * 100 if peak > 0 else 0
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        # 計算波動率（月報酬標準差）
        if len(daily_values) > 1:
            values = [dv['portfolio_value'] for dv in daily_values if dv['portfolio_value'] > 0]
            if len(values) > 1:
                returns = pd.Series(values).pct_change().dropna()
                monthly_vol = returns.std() * (252 ** 0.5) * 100  # 年化波動率
            else:
                monthly_vol = 0
        else:
            monthly_vol = 0
        
        # 計算夏普比率 (假設無風險利率 1%)
        risk_free_rate = 1.0
        sharpe_ratio = (cagr - risk_free_rate) / monthly_vol if monthly_vol > 0 else 0
        
        # 計算每筆投資的報酬
        trade_results = []
        for inv in investment_log:
            inv_date = inv['date']
            future_values = [dv['portfolio_value'] for dv in daily_values 
                           if dv['date'] >= inv_date and dv['portfolio_value'] > 0]
            if future_values:
                final_val = future_values[-1]
                profit = final_val - inv['amount']
                ret_pct = (profit / inv['amount'] * 100) if inv['amount'] > 0 else 0
                trade_results.append({
                    'date': inv['date'],
                    'amount': inv['amount'],
                    'current_value': round(final_val, 2),
                    'profit': round(profit, 2),
                    'return_pct': round(ret_pct, 2)
                })
        
        # 勝率
        winning_trades = sum(1 for t in trade_results if t['profit'] > 0)
        win_rate = (winning_trades / len(trade_results) * 100) if trade_results else 0
        
        # 準備圖表數據
        chart_data = {
            "dates": [dv['date'] for dv in daily_values],
            "portfolio_values": [dv['portfolio_value'] for dv in daily_values],
            "cumulative_invested": [
                sum(log['amount'] for log in investment_log if log['date'] <= dv['date'])
                for dv in daily_values
            ],
            "pe_ratios": [dv['pe_ratio'] for dv in daily_values],
            "investment_dates": [inv['date'] for inv in investment_log],
            "pe_threshold": invest_on_pe_threshold
        }
        
        return {
            "status": "success",
            "ticker": ticker.replace('.TW', ''),
            "start_date": start_date,
            "end_date": end_date,
            "initial_amount": initial_amount,
            "monthly_amount": monthly_amount,
            "total_invested": round(total_invested, 2),
            "final_value": round(final_value, 2),
            "total_profit": round(total_profit, 2),
            "total_return_pct": round(total_return_pct, 2),
            "cagr": round(cagr, 2),
            "max_drawdown": round(max_drawdown, 2),
            "volatility": round(monthly_vol, 2),
            "sharpe_ratio": round(sharpe_ratio, 2),
            "invest_months": invest_months,
            "win_rate": round(win_rate, 1),
            "final_price": round(final_price, 2),
            "investment_log": investment_log,
            "trade_results": trade_results[-10:],
            "chart_data": chart_data,
            "kpi_cards": {
                "total_invested": round(total_invested, 2),
                "final_value": round(final_value, 2),
                "total_profit": round(total_profit, 2),
                "total_return_pct": round(total_return_pct, 2),
                "cagr": round(cagr, 2),
                "max_drawdown": round(max_drawdown, 2),
                "volatility": round(monthly_vol, 2),
                "sharpe_ratio": round(sharpe_ratio, 2),
                "win_rate": round(win_rate, 1),
                "invest_months": invest_months
            }
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_pe_data_from_ticker(stock_code, target_date=None):
    """
    從 stock_PE 模組取得 PE 數據
    
    Args:
        stock_code: 股票代號
        target_date: 目標日期（pd.Timestamp 或 str），如果為 None 則獲取最新 PE
    
    Returns:
        dict: 包含 pe_ratio 等資訊，失敗回傳 None
    """
    try:
        import stock_PE
        import pandas as pd
        
        # 獲取歷史 PE 數據
        df = stock_PE.get_stock_data(stock_code)
        
        if df is None or df.empty:
            print(f"❌ PE 數據獲取失敗 - 股票 {stock_code}: 資料庫無資料")
            return None
        
        # 轉換日期格式
        df['date'] = pd.to_datetime(df['date'])
        df['pe_ratio'] = pd.to_numeric(df['pe_ratio'], errors='coerce')
        df = df.dropna(subset=['pe_ratio'])
        
        if df.empty:
            print(f"❌ PE 數據獲取失敗 - 股票 {stock_code}: 無有效 PE 數據")
            return None
        
        # 如果指定了目標日期，獲取該日期的 PE 數據
        if target_date:
            if isinstance(target_date, str):
                target_date = pd.Timestamp(target_date)
            
            # 找到目標日期之前（包含）的最新 PE 數據
            past_data = df[df['date'] <= target_date]
            if past_data.empty:
                print(f"⚠️ 股票 {stock_code} 在 {target_date.strftime('%Y-%m-%d')} 無 PE 數據")
                return None
            
            latest_pe_row = past_data.iloc[-1]
            pe_ratio = float(latest_pe_row['pe_ratio'])
            pe_date = latest_pe_row['date'].strftime('%Y-%m-%d')
        else:
            # 獲取最新 PE 數據
            latest_pe_row = df.iloc[-1]
            pe_ratio = float(latest_pe_row['pe_ratio'])
            pe_date = latest_pe_row['date'].strftime('%Y-%m-%d')
        
        result = {
            'pe_ratio': pe_ratio,
            'date': pe_date,
        }
        
        print(f"✅ PE 數據獲取成功 - 股票 {stock_code}: PE={pe_ratio:.2f} (日期: {pe_date})")
        return result
        
    except Exception as e:
        print(f"❌ PE 數據獲取異常 - 股票 {stock_code}: {e}")
        return None
def run_pe_accumulate_backtest(ticker="2330.TW", start_date="2020-01-01", end_date="2026-05-28", 
                               monthly_accumulate=5000, invest_on_pe_threshold=15):
    '''
    PE ?�ɲֿn�����^�� (PE Timing Accumulate Backtest)
    
    �����޿�G
    1. �C��۰ʲֿn���w���B�]�Ҧp�C��s 5000 �쵥�ݦ��^
    2. �� PE < ���e�ɡA�N���ݦ������Ҧ����@���ʧ�J
    3. ��J�᭫�s�}�l�ֿn
    
    Args:
        ticker: �Ѳ��N�� (�p "2330.TW")
        start_date: �}�l���
        end_date: �������
        monthly_accumulate: �C��ֿn���B
        invest_on_pe_threshold: PE ���e�A�C�󦹭Ȯɤ@���ʧ�J
    
    Returns:
        dict: �^�����G
    '''
    try:
        # ���o�Ѳ��ƾ�
        df_data = fetch_series(ticker, start_date, end_date)
        px = df_data["Adj Close"]
        
        # �p�����d��
        start_dt = pd.Timestamp(start_date)
        end_dt = pd.Timestamp(end_date)
        
        # �i�u�ơj�b�^���}�l�e�@��������Ҧ����v PE �ƾ�
        pe_cache = build_pe_cache(ticker.replace('.TW', ''), start_date, end_date)
        
        # �ͦ�������C���]�C��Ĥ@�ӥ����^
        trading_calendar = px.index
        investment_dates = []
        
        # ���o�C��Ĥ@�ӥ����
        monthly_first_days = pd.date_range(start=start_dt, end=end_dt, freq='MS')
        for month_day in monthly_first_days:
            # ���Ӥ�Ĥ@�ӥ����
            first_trading_day = trading_calendar[trading_calendar >= month_day]
            if len(first_trading_day) > 0:
                investment_dates.append(first_trading_day[0])
        
        # ����^��
        total_invested = 0  # �֭p��J���B
        total_shares = 0    # �֭p�����Ѽ�
        investment_log = []   # ���O��
        
        current_shares = 0
        waiting_pool = 0  # ���ݦ����B
        daily_values = []
        monthly_accumulate_dates = []  # �O���C��ֿn�����
        
        for i, date in enumerate(px.index):
            # �p�����骺�զX����
            if current_shares > 0:
                value = current_shares * px.loc[date]
            else:
                value = 0
            
            # ������� PE
            current_pe = None
            if pe_cache:
                current_pe = get_pe_for_date(pe_cache, date)
            
            daily_values.append({
                'date': date.strftime('%Y-%m-%d'),
                'price': round(float(px.loc[date]), 2),
                'portfolio_value': round(value, 2),
                'pe_ratio': round(current_pe, 2) if current_pe else None,
                'waiting_pool': round(waiting_pool, 2)
            })
            
            # �ˬd�O�_�O�ֿn��]�C��Ĥ@�ӥ����^
            if date in investment_dates:
                # �C����ֿn����쵥�ݦ�
                waiting_pool += monthly_accumulate
                monthly_accumulate_dates.append({
                    'date': date.strftime('%Y-%m-%d'),
                    'amount': monthly_accumulate,
                    'pool_total': round(waiting_pool, 2),
                    'pe_ratio': round(current_pe, 2) if current_pe else None
                })
                
                # �ˬd PE ���e�A�p�G�C����e�h�@���ʧ�J
                should_invest = True
                if current_pe is not None and current_pe >= invest_on_pe_threshold:
                    should_invest = False
                
                if should_invest and waiting_pool > 0:
                    # �@���ʧ�J���ݦ������Ҧ���
                    invest_amount = waiting_pool
                    
                    # �p��R�J�Ѽơ]����ƪѡ^
                    shares_to_buy = int(invest_amount / px.loc[date])
                    
                    if shares_to_buy > 0:
                        cost = shares_to_buy * px.loc[date]
                        current_shares += shares_to_buy
                        total_invested += cost
                        waiting_pool -= cost  # �����w��J���B
                        
                        investment_log.append({
                            'date': date.strftime('%Y-%m-%d'),
                            'price': round(float(px.loc[date]), 2),
                            'amount': round(cost, 2),
                            'shares': shares_to_buy,
                            'total_shares': current_shares,
                            'total_invested': round(total_invested, 2),
                            'pe_ratio': round(current_pe, 2) if current_pe else None,
                            'waiting_pool_before': round(waiting_pool + cost, 2),
                            'status': '���'
                        })
                    else:
                        # PE �C�����B�����R�@��
                        investment_log.append({
                            'date': date.strftime('%Y-%m-%d'),
                            'price': round(float(px.loc[date]), 2),
                            'amount': 0,
                            'shares': 0,
                            'total_shares': current_shares,
                            'total_invested': round(total_invested, 2),
                            'pe_ratio': round(current_pe, 2) if current_pe else None,
                            'waiting_pool': round(waiting_pool, 2),
                            'status': '���B����'
                        })
                else:
                    # PE �Ӱ��A���L���
                    investment_log.append({
                        'date': date.strftime('%Y-%m-%d'),
                        'price': round(float(px.loc[date]), 2),
                        'amount': 0,
                        'shares': 0,
                        'total_shares': current_shares,
                        'total_invested': round(total_invested, 2),
                        'pe_ratio': round(current_pe, 2) if current_pe else None,
                        'waiting_pool': round(waiting_pool, 2),
                        'status': '���L'
                    })
        
        # �p��̲׵��G
        final_value = daily_values[-1]['portfolio_value'] if daily_values else 0
        final_price = daily_values[-1]['price'] if daily_values else 0
        total_profit = final_value - total_invested
        total_return_pct = (total_profit / total_invested * 100) if total_invested > 0 else 0
        
        # �p���ꦸ��
        invest_count = len([inv for inv in investment_log if inv['status'] == '���'])
        
        # �p��~�Ƴ��S�v (CAGR)
        years = (end_dt - start_dt).days / 365.25
        if years > 0 and total_invested > 0:
            cagr = ((final_value / total_invested) ** (1 / years) - 1) * 100 if final_value > total_invested else \
                   -((1 - final_value / total_invested) ** (1 / years)) * 100
        else:
            cagr = 0
        
        # �p��̤j�^�M
        peak = 0
        max_drawdown = 0
        for dv in daily_values:
            if dv['portfolio_value'] > peak:
                peak = dv['portfolio_value']
            drawdown = (peak - dv['portfolio_value']) / peak * 100 if peak > 0 else 0
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        # �p��i�ʲv
        if len(daily_values) > 1:
            values = [dv['portfolio_value'] for dv in daily_values if dv['portfolio_value'] > 0]
            if len(values) > 1:
                returns = pd.Series(values).pct_change().dropna()
                monthly_vol = returns.std() * (252 ** 0.5) * 100
            else:
                monthly_vol = 0
        else:
            monthly_vol = 0
        
        # �p��L����v
        risk_free_rate = 1.0
        sharpe_ratio = (cagr - risk_free_rate) / monthly_vol if monthly_vol > 0 else 0
        
        # �p��C����ꪺ���S
        trade_results = []
        for inv in investment_log:
            if inv['status'] != '���':
                continue
            inv_date = inv['date']
            future_values = [dv['portfolio_value'] for dv in daily_values 
                           if dv['date'] >= inv_date and dv['portfolio_value'] > 0]
            if future_values:
                final_val = future_values[-1]
                profit = final_val - inv['amount']
                ret_pct = (profit / inv['amount'] * 100) if inv['amount'] > 0 else 0
                trade_results.append({
                    'date': inv['date'],
                    'amount': inv['amount'],
                    'current_value': round(final_val, 2),
                    'profit': round(profit, 2),
                    'return_pct': round(ret_pct, 2)
                })
        
        # �Ӳv
        winning_trades = sum(1 for t in trade_results if t['profit'] > 0)
        win_rate = (winning_trades / len(trade_results) * 100) if trade_results else 0
        
        # �ǳƹϪ��ƾ�
        chart_data = {
            "dates": [dv['date'] for dv in daily_values],
            "portfolio_values": [dv['portfolio_value'] for dv in daily_values],
            "cumulative_invested": [
                sum(log['amount'] for log in investment_log if log['date'] <= dv['date'])
                for dv in daily_values
            ],
            "pe_ratios": [dv['pe_ratio'] for dv in daily_values],
            "waiting_pools": [dv['waiting_pool'] for dv in daily_values],
            "investment_dates": [inv['date'] for inv in investment_log if inv['status'] == '���'],
            "pe_threshold": invest_on_pe_threshold
        }
        
        return {
            "status": "success",
            "ticker": ticker.replace('.TW', ''),
            "start_date": start_date,
            "end_date": end_date,
            "monthly_accumulate": monthly_accumulate,
            "pe_threshold": invest_on_pe_threshold,
            "total_invested": round(total_invested, 2),
            "final_value": round(final_value, 2),
            "total_profit": round(total_profit, 2),
            "total_return_pct": round(total_return_pct, 2),
            "cagr": round(cagr, 2),
            "max_drawdown": round(max_drawdown, 2),
            "volatility": round(monthly_vol, 2),
            "sharpe_ratio": round(sharpe_ratio, 2),
            "invest_count": invest_count,
            "win_rate": round(win_rate, 1),
            "final_price": round(final_price, 2),
            "investment_log": investment_log,
            "trade_results": trade_results[-10:],
            "monthly_accumulate_log": monthly_accumulate_dates,
            "chart_data": chart_data,
            "kpi_cards": {
                "total_invested": round(total_invested, 2),
                "final_value": round(final_value, 2),
                "total_profit": round(total_profit, 2),
                "total_return_pct": round(total_return_pct, 2),
                "cagr": round(cagr, 2),
                "max_drawdown": round(max_drawdown, 2),
                "volatility": round(monthly_vol, 2),
                "sharpe_ratio": round(sharpe_ratio, 2),
                "win_rate": round(win_rate, 1),
                "invest_count": invest_count
            }
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}
