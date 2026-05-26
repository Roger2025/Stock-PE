# ==========================================
# ⚠️ 伺服器防當機設定 (必須在最前面，且只能宣告一次)
# ==========================================
import matplotlib
matplotlib.use('Agg') # 強制使用無外觀的背景繪圖引擎
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

import os
import requests
import pymysql
import time
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from dotenv import load_dotenv
import platform
from datetime import datetime

# ==========================================
# 0. 全域環境與視覺設定
# ==========================================
load_dotenv()


# # --- 終極字體解決方案 (本地打包 + 自動保底) ---  用matplotlib再開啟
# def set_mpl_fonts():
#     import os
#     import platform
#     import matplotlib.font_manager as fm

#     # --- 關鍵：路徑要加上 static/ ---
#     current_dir = os.path.dirname(os.path.abspath(__file__))
#     # 這裡多加一個 "static"
#     local_font_path = os.path.join(current_dir, "static", "myfont.ttf") 
#     print(f"--- 偵測字體路徑: {os.path.abspath(local_font_path)} ---")
#     print(f"--- 檔案是否存在: {os.path.exists(local_font_path)} ---")
#     if platform.system() == 'Windows':
#         plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'Arial']
#     else:
#         if os.path.exists(local_font_path):
#             try:
#                 fm.fontManager.addfont(local_font_path)
#                 prop = fm.FontProperties(fname=local_font_path)
#                 plt.rcParams['font.sans-serif'] = [prop.get_name(), 'sans-serif']
#                 print(f"✅ 成功從 static 載入字體: {prop.get_name()}")
#             except:
#                 plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
#         else:
#             print(f"⚠️ 找不到字體，路徑檢查: {local_font_path}")
#             plt.rcParams['font.sans-serif'] = ['DejaVu Sans']

# # 執行設定
# set_mpl_fonts()

conn = None
cursor = None

# ==========================================
# 1. 資料庫連線模組
# ==========================================
def open_db():
    global conn, cursor
    try:
        host = os.getenv("db_host").strip()
        user = os.getenv("db_user").strip()
        password = os.getenv("db_password").strip()
        database = os.getenv("db_database").strip()
        port = int(os.getenv("db_port", 21697))

        conn = pymysql.connect(
            host=host,
            password=password,
            port=port,
            user=user,
            database=database,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
            ssl={'ssl': {}}
        )
        cursor = conn.cursor()
        print(f"✅ 連線 Aiven 成功！")
        create_stock_table()
    except Exception as e:
        print(f"❌ 資料庫開啟失敗: {e}")

def get_stock_data(stock_id):
    try:
        open_db()
        sql_str = """
        SELECT date, pe_ratio, stock_name 
        FROM stock_pe_ratio 
        WHERE stock_id = %s 
        ORDER BY date ASC
        """
        cursor.execute(sql_str, (stock_id,))
        datas = cursor.fetchall()
        return pd.DataFrame(datas)
    except Exception as e:
        print(f"❌ 讀取數據錯誤: {e}")
        return pd.DataFrame()
    finally:
        close_db()    

def create_stock_table():
    global conn, cursor
    if not cursor: return
    sql = """
    CREATE TABLE IF NOT EXISTS stock_pe_ratio (
        id INT AUTO_INCREMENT PRIMARY KEY,
        date DATE NOT NULL,
        stock_id VARCHAR(10) NOT NULL,
        stock_name VARCHAR(20),
        pe_ratio DECIMAL(10, 2),
        UNIQUE KEY unique_stock_date (date, stock_id),
        INDEX idx_stock (stock_id),
        INDEX idx_date (date)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    try:
        cursor.execute(sql)
        conn.commit()
    except Exception as e:
        print(f"❌ 建立資料表失敗: {e}")

def close_db():
    global conn, cursor
    try:
        if cursor: cursor.close()
        if conn: conn.close()
    except Exception as e:
        print(f"❌ 關閉錯誤: {e}")


# ==========================================
# 2. 爬蟲與資料清洗模組
# ==========================================
# 透過API抓取所有股票代號跟名稱
def get_pe_data(stock_id):
    """
    取得股票最新 PE 數據與等級（基於過去 5 年歷史百分位）
    
    Args:
        stock_id: 股票代碼
    
    Returns:
        dict: 包含 pe_ratio, valuation, percentile, insight 等資訊，失敗回傳 None
    """
    try:
        # 從資料庫取得歷史 PE 資料
        df = get_stock_data(stock_id)
        
        if df is None or df.empty:
            print(f"⚠️ 資料庫無 {stock_id} 資料，改從 API 抓取...")
            # 如果資料庫沒有資料，直接從證交所 API 抓取最新 PE
            try:
                today = datetime.now().strftime('%Y%m%d')
                json_data = get_stock_history_data(stock_id, today)
                if json_data and json_data.get('stat') == 'OK':
                    fields = json_data.get('fields', [])
                    pe_index = fields.index('本益比') if '本益比' in fields else 3
                    raw_data = json_data['data']
                    
                    if raw_data and len(raw_data) > 0:
                        pe_str = raw_data[0][pe_index]
                        if pe_str and pe_str != '-':
                            pe_ratio = float(pe_str)
                            if pe_ratio > 0:
                                # 沒有歷史資料時，返回 PE 值但不給等級
                                return {
                                    'pe_ratio': pe_ratio,
                                    'valuation': '未知',
                                    'percentile': None,
                                    'insight': f'{stock_id} 當前 PE={pe_ratio:.2f}，暫無歷史資料比較。',
                                    'has_history': False,
                                }
            except Exception as e:
                print(f"❌ API 抓取 {stock_id} 失敗: {e}")
            
            return None
        
        # 過濾掉錯誤的日期（只保留今年以內的資料）
        current_year = datetime.now().year
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df = df.dropna(subset=['date'])
        df = df[df['date'].dt.year <= current_year]
        
        if df.empty:
            return None
        
        # 取得最新 PE 與歷史資料
        df['pe_ratio'] = pd.to_numeric(df['pe_ratio'], errors='coerce')
        df = df.dropna(subset=['pe_ratio'])
        
        if len(df) < 10:
            return None
        
        latest_pe = float(df['pe_ratio'].iloc[-1])
        latest_date = str(df['date'].iloc[-1].date())
        
        # 計算過去 5 年的歷史統計區間（像河流圖那樣）
        # 取最近 5 年（或所有可用資料）
        five_years_ago = datetime.now() - pd.DateOffset(years=5)
        recent_df = df[df['date'] >= five_years_ago]
        
        if len(recent_df) < 5:
            # 如果 5 年資料不足，使用所有可用資料
            recent_df = df
        
        historical_pe_list = recent_df['pe_ratio'].tolist()
        latest_pe = float(df['pe_ratio'].iloc[-1])
        
        # 計算統計數據
        pe_min = min(historical_pe_list)
        pe_max = max(historical_pe_list)
        pe_avg = sum(historical_pe_list) / len(historical_pe_list)
        
        # 計算標準差來劃分五個區域
        pe_std = (sum((pe - pe_avg) ** 2 for pe in historical_pe_list) / len(historical_pe_list)) ** 0.5
        
        # 五個區域界線（類似河流圖）
        # 危險區 > avg + 2*std
        # 昂貴區 > avg + std
        # 合理區 > avg - std
        # 便宜區 > avg - 2*std
        # 超跌區 <= avg - 2*std
        danger_zone = pe_avg + 2 * pe_std  # 危險區
        expensive_zone = pe_avg + pe_std   # 昂貴區
        fair_zone = pe_avg - pe_std        # 合理區
        cheap_zone = pe_avg - 2 * pe_std   # 便宜區
        
        # 根據當前 PE 落在哪個區間來評判
        if latest_pe > danger_zone:
            grade = 'E'
            valuation = '危險'
            insight = f'{stock_id} 當前 PE={latest_pe:.2f}，處於危險區（> {danger_zone:.2f}），極高估值，建議獲利了結。'
        elif latest_pe > expensive_zone:
            grade = 'D'
            valuation = '昂貴'
            insight = f'{stock_id} 當前 PE={latest_pe:.2f}，處於昂貴區（> {expensive_zone:.2f}），估值偏高，停止追高。'
        elif latest_pe > fair_zone:
            grade = 'C'
            valuation = '合理'
            insight = f'{stock_id} 當前 PE={latest_pe:.2f}，處於合理區（> {fair_zone:.2f}），合理估值，持股續抱。'
        elif latest_pe > cheap_zone:
            grade = 'B'
            valuation = '便宜'
            insight = f'{stock_id} 當前 PE={latest_pe:.2f}，處於便宜區（> {cheap_zone:.2f}），估值偏低，分批佈局。'
        else:
            grade = 'A'
            valuation = '超跌'
            insight = f'{stock_id} 當前 PE={latest_pe:.2f}，處於超跌區（< {cheap_zone:.2f}），極低估值，價值浮現。'
        
        # 計算各區間佔比（用於河流圖顯示）
        zones = {
            'danger': sum(1 for pe in historical_pe_list if pe > danger_zone),
            'expensive': sum(1 for pe in historical_pe_list if expensive_zone < pe <= danger_zone),
            'fair': sum(1 for pe in historical_pe_list if fair_zone < pe <= expensive_zone),
            'cheap': sum(1 for pe in historical_pe_list if cheap_zone < pe <= fair_zone),
            'super_deal': sum(1 for pe in historical_pe_list if pe <= cheap_zone),
        }
        total = len(historical_pe_list)
        zones_pct = {k: round(v / total * 100) for k, v in zones.items()}
        
        return {
            'pe_ratio': latest_pe,
            'date': latest_date,
            'grade': grade,
            'valuation': valuation,
            'insight': insight,
            'has_history': True,
            'historical_min': pe_min,
            'historical_max': pe_max,
            'historical_avg': round(pe_avg, 2),
            'historical_std': round(pe_std, 2),
            # 五個區域界線（給前端河流圖用）
            'zones': {
                'danger': round(danger_zone, 2),
                'expensive': round(expensive_zone, 2),
                'fair': round(fair_zone, 2),
                'cheap': round(cheap_zone, 2),
            },
            # 各區間佔比
            'zone_distribution': zones_pct,
        }
    except Exception as e:
        print(f"❌ 取得 {stock_id} PE 數據失敗: {e}")
        return None


def get_stock_map():
    url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    try:
        res = requests.get(url, timeout=10)
        return {item['Code']: item['Name'] for item in res.json()}
    except:
        return {}

def get_stock_history_data(stock_id, date_str):
    url = f"https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU?date={date_str}&stockNo={stock_id}&response=json"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=15)
        return res.json() if res.status_code == 200 else None
    except:
        return None

def write_stock_db(stock_id, date_str, stock_map):
    global conn, cursor
    json_data = get_stock_history_data(stock_id, date_str)
    if not json_data or json_data.get('stat') != 'OK': return 0
    stock_name = stock_map.get(stock_id, stock_id)
    raw_datas = json_data['data']
    fields = json_data.get('fields', [])
    # 加if in不讓程式抱錯
    # 這寫法可動態抓取本益比位置 克服證交所改位置的問題
    pe_index = fields.index('本益比') if '本益比' in fields else 3
    clean_data = []
    for item in raw_datas:
        try:
            raw_date = item[0] 
            western_year = int(raw_date.split('年')[0]) + 1911
            month_day = raw_date.split('年')[1].replace('月', '-').replace('日', '')
            western_date = f"{western_year}-{month_day}"
            pe_raw = item[pe_index].strip()
            pe_ratio = float(pe_raw.replace(',', '')) if pe_raw not in ["-", ""] else None
            clean_data.append((western_date, stock_id, stock_name, pe_ratio))
        # 有錯誤就下一檔
        except: continue
    sql = "INSERT IGNORE INTO stock_pe_ratio (date, stock_id, stock_name, pe_ratio) VALUES (%s, %s, %s, %s)"
    try:
        size = cursor.executemany(sql, clean_data)
        conn.commit()
        return size
    except:
        return 0
    
# 新增Echart功能 先抓數據 (極致純淨小數點修正版)
def get_echarts_data(stock_id, start_date='2006-01-01', end_date='2027-12-31', 
                     smooth_days=5, std_high=1.5, std_mid=0.5):
    """
    計算河流圖數據，並以 Dictionary (JSON) 格式回傳。
    強制將所有輸出的標準差區間與數值流精確鎖定至小數點後兩位。
    """
    # 1. 抓取資料
    df = get_stock_data(stock_id)
    if df is None or df.empty: 
        return None

    # 2. 清洗資料
    stock_name = df['stock_name'].iloc[0] if 'stock_name' in df.columns and not df['stock_name'].empty else stock_id
    df['date'] = pd.to_datetime(df['date'], format='%Y-%m-%d', errors='coerce')
    df = df.dropna(subset=['date']).sort_values('date')
    df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]
    
    df['pe_ratio'] = pd.to_numeric(df['pe_ratio'], errors='coerce')
    df = df.dropna(subset=['pe_ratio']).set_index('date')

    if len(df) < 2: 
        return None

    # 3. 計算平滑線與估值門檻
    pe_smooth = df['pe_ratio'].rolling(window=smooth_days, min_periods=1).mean()
    avg_pe = float(df['pe_ratio'].mean())
    std_pe = float(df['pe_ratio'].std(ddof=0))
    
    # 🚀 建立門檻值：完整覆蓋前端樣板所有可能的標籤取用名稱，嚴格鎖定兩位小數
    lv = {
        '極高': float(round(avg_pe + std_high * std_pe, 2)),
        '偏高': float(round(avg_pe + std_mid * std_pe, 2)),
        '合理': float(round(avg_pe, 2)),
        '偏低': float(round(avg_pe - std_mid * std_pe, 2)),
        '極低': float(round(avg_pe - std_high * std_pe, 2)),
        # 完美對應 result.html 呈現的區段名稱
        '危險區': float(round(avg_pe + std_high * std_pe, 2)),
        '昂貴區': float(round(avg_pe + std_mid * std_pe, 2)),
        '合理區': float(round(avg_pe, 2)),
        '便宜區': float(round(avg_pe - std_mid * std_pe, 2)),
        '超跌區': float(round(avg_pe - std_high * std_pe, 2))
    }

    # 4. 封裝序列數據，清洗 NaN 並套用 round(2)
    clean_pe_smooth = [round(x, 2) if pd.notnull(x) else None for x in pe_smooth.tolist()]

    chart_data = {
        "stock_name": stock_name,
        "stock_id": stock_id,
        "dates": df.index.strftime('%Y-%m-%d').tolist(), 
        "pe_smooth": clean_pe_smooth, 
        "levels": lv,
        "config": {
            "high_multiplier": std_high,
            "mid_multiplier": std_mid
        }
    }
    
    return chart_data

# --- 原本的 plot_stock_pe_trend 可以註解掉或關閉 ---
# def plot_stock_pe_trend(...): 
#    ... (這裡面的程式碼暫時不用跑了)


# ==========================================
# 3. 專業五階段估值河流圖模組
# ==========================================
# def plot_stock_pe_trend(stock_id, start_date='2006-01-01', end_date='2027-12-31', 
#                         smooth_days=5, std_high=1.5, std_mid=0.5, dpi=100):
    
#     df = get_stock_data(stock_id)
#     if df.empty: return

#     stock_name = df['stock_name'].iloc[0] if df['stock_name'].iloc[0] else stock_id
#     df['date'] = pd.to_datetime(df['date'], errors='coerce')
#     df = df.dropna(subset=['date']).sort_values('date')
#     df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]
#     df['pe_ratio'] = pd.to_numeric(df['pe_ratio'], errors='coerce')
#     df = df.dropna(subset=['pe_ratio']).set_index('date')

#     if len(df) < 2: return

#     df['pe_smooth'] = df['pe_ratio'].rolling(window=smooth_days, min_periods=1).mean()
#     avg_pe = df['pe_ratio'].mean()
#     std_pe = df['pe_ratio'].std()
    
#     lv = {
#         '極高': avg_pe + std_high * std_pe,
#         '偏高': avg_pe + std_mid * std_pe,
#         '合理': avg_pe,
#         '偏低': avg_pe - std_mid * std_pe,
#         '極低': avg_pe - std_high * std_pe
#     }

#     fig, ax = plt.subplots(figsize=(22, 12), facecolor='#FCFCFC')
    
#     ax.fill_between(df.index, lv['極高'], lv['極高']*1.5, color='#FF595E', alpha=0.3)
#     ax.fill_between(df.index, lv['偏高'], lv['極高'], color='#FFCA3A', alpha=0.2)
#     ax.fill_between(df.index, lv['偏低'], lv['偏高'], color='#F8FFE5', alpha=0.2)
#     ax.fill_between(df.index, lv['極低'], lv['偏低'], color='#8AC926', alpha=0.2)
#     ax.fill_between(df.index, 0, lv['極低'], color='#1982C4', alpha=0.15)

#     ax.plot(df.index, df['pe_smooth'], color='#1D3557', linewidth=2.5, zorder=5)

#     # ==========================================
#     # 🎯 補回：最高、最低與最新數據標示
#     # ==========================================
#     # 1. 原始的最高與最低點
#     max_val, max_dt = df['pe_ratio'].max(), df['pe_ratio'].idxmax()
#     min_val, min_dt = df['pe_ratio'].min(), df['pe_ratio'].idxmin()
#     ax.scatter([max_dt, min_dt], [max_val, min_val], color=['#D90429', '#023E8A'], s=120, zorder=10, edgecolor='white')

#     # 加上最高最低的數字標籤
#     ax.annotate(f'最高: {max_val:.2f}', xy=(max_dt, max_val), xytext=(0, 15),
#                 textcoords='offset points', ha='center', color='#D90429', fontweight='bold', fontsize=14)
#     ax.annotate(f'最低: {min_val:.2f}', xy=(min_dt, min_val), xytext=(0, -20),
#                 textcoords='offset points', ha='center', color='#023E8A', fontweight='bold', fontsize=14)

#     # 2. 補上「最新數據」的點與標籤
#     current_dt = df.index[-1]
#     current_val = df['pe_ratio'].iloc[-1]
    
#     ax.scatter(current_dt, current_val, color='#FCA311', s=150, zorder=11, edgecolor='white')
#     ax.annotate(f'最新: {current_val:.2f}', xy=(current_dt, current_val), xytext=(15, 0),
#                 textcoords='offset points', ha='left', va='center', color='#FCA311', fontweight='bold', fontsize=14,
#                 bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#FCA311", lw=1.5, alpha=0.9))
#     # ==========================================

#     table_data = [
#         ["極高階段", f"{lv['極高']:.2f} ↑", "獲利了結"],
#         ["偏高階段", f"{lv['合理']:.2f}-{lv['極高']:.2f}", "停止追高"],
#         ["合理階段", f"{lv['偏低']:.2f}-{lv['合理']:.2f}", "持股續抱"],
#         ["偏低階段", f"{lv['極低']:.2f}-{lv['偏低']:.2f}", "建立持股"],
#         ["極低階段", f"{lv['極低']:.2f} ↓", "價值佈局"]
#     ]

#     the_table = ax.table(
#         cellText=table_data, 
#         colLabels=["估值階段", "門檻值", "建議"], 
#         loc='lower right', 
#         cellLoc='center', 
#         bbox=[0.68, 0.05, 0.30, 0.22]
#     )

#     the_table.auto_set_font_size(False)
#     the_table.set_fontsize(13) 
    
#     for (row, col), cell in the_table.get_celld().items():
#         cell.set_alpha(0.7) 
#         if row == 0:
#             cell.set_text_props(weight='bold', color='white')
#             cell.set_facecolor('#1D3557')
#             cell.set_alpha(0.9)

#     ax.set_title(f'{stock_name} ({stock_id}) 歷史五階段估值河流圖', fontsize=26, fontweight='bold', pad=30)
#     ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
#     ax.grid(True, linestyle='--', alpha=0.3)
    
#     plt.tight_layout(pad=3.0)
    
#     filename = f"{stock_id}_Ultimate_RiverMap.png"
#     plt.savefig(filename, dpi=dpi, bbox_inches='tight')
#     plt.close(fig) 
    
#     # 順手幫你加上垃圾回收，確保它永遠不會爆記憶體
#     import gc
#     gc.collect()

# ==========================================
# 4. 主程式入口
# ==========================================
if __name__ == "__main__":
    TARGET_ID = "2454"
    IMAGE_DPI = 100 
    open_db()
    if cursor:
        print(get_echarts_data(TARGET_ID)) , #dpi=IM_DPI沒畫圖先拿掉
        close_db()

