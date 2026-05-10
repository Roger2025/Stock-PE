import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

def _scalar(x):
    try:
        return x.item()
    except AttributeError:
        return float(x)

def fetch_series(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
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