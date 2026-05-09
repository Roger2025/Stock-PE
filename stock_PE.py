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
from sqlalchemy import create_engine
from dotenv import load_dotenv
import platform

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
    
# 新增Echart功能 先抓數據
def get_echarts_data(stock_id, start_date='2006-01-01', end_date='2027-12-31', 
                     smooth_days=5, std_high=1.5, std_mid=0.5):
    """
    計算河流圖數據，並以 Dictionary (JSON) 格式回傳，不進行實體繪圖。
    """
    # 1. 抓取資料 (沿用原本邏輯)
    df = get_stock_data(stock_id)
    if df.empty: return None

    # 2. 清洗資料
    stock_name = df['stock_name'].iloc[0] if df['stock_name'].iloc[0] else stock_id
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date']).sort_values('date')
    df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]
    df['pe_ratio'] = pd.to_numeric(df['pe_ratio'], errors='coerce')
    df = df.dropna(subset=['pe_ratio']).set_index('date')

    if len(df) < 2: return None

    # 3. 計算平滑線與估值區間 (原本你的計算邏輯)
    pe_smooth = df['pe_ratio'].rolling(window=smooth_days, min_periods=1).mean()
    avg_pe = df['pe_ratio'].mean()
    std_pe = df['pe_ratio'].std()
    
    # 建立五個區間的門檻值
    lv = {
        '極高': round(avg_pe + std_high * std_pe, 2),
        '偏高': round(avg_pe + std_mid * std_pe, 2),
        '合理': round(avg_pe, 2),
        '偏低': round(avg_pe - std_mid * std_pe, 2),
        '極低': round(avg_pe - std_high * std_pe, 2)
    }

    # 4. 封裝成 ECharts 需要的數據格式
    # ECharts 需要列表 (List) 格式，所以我們用 .tolist() 轉換
    chart_data = {
        "stock_name": stock_name,
        "stock_id": stock_id,
        "dates": df.index.strftime('%Y-%m-%d').tolist(), # 日期轉成字串
        "pe_smooth": [round(x, 2) for x in pe_smooth.tolist()], # 平滑後的 PE
        "levels": lv # 五個區間的基準值
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

