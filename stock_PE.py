# ==========================================
# ⚠️ 伺服器防當機設定 (必須在最前面，且只能宣告一次)
# ==========================================
import matplotlib
matplotlib.use('Agg') # 強制使用無外觀的背景繪圖引擎，絕對不能少！
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

import os
import requests
import pymysql
import time
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv

# ==========================================
# 0. 全域環境與視覺設定
# ==========================================
# 載入環境變數
load_dotenv()

# 設定字體防止中文亂碼
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei'] 
plt.rcParams['axes.unicode_minus'] = False


# ==========================================
# 1. 資料庫連線模組 (使用 PyMySQL 處理寫入)
# ==========================================
def open_db():
    global conn, cursor
    conn = None
    cursor = None
    
    try:
        # 確保沒有隱形空格
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
            ssl={'ssl': {}}  # Aiven 強制要求
        )
        cursor = conn.cursor()
        print(f"✅ 連線 Aiven 成功！ (Host: {host})")
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
        datas=cursor.fetchall()
        df=pd.DataFrame(datas)
        return df
    except Exception as e:
        print(f"錯誤訊息:{e}")
    finally:
        close_db()    
    

def create_stock_table():
    global conn, cursor
    if not cursor: 
        return

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
        print("📊 資料表檢查/建立完成。")
    except Exception as e:
        print(f"❌ 建立資料表失敗: {e}")

def close_db():
    global conn, cursor
    try:
        if cursor: cursor.close()
        if conn: conn.close()
        print("🔒 資料庫連線已安全關閉。")
    except Exception as e:
        print(f"❌ 關閉錯誤: {e}")


# ==========================================
# 2. 爬蟲與資料清洗模組
# ==========================================
def get_stock_map():
    url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    try:
        res = requests.get(url, timeout=10)
        return {item['Code']: item['Name'] for item in res.json()}
    except Exception as e:
        print(f"⚠️ 無法取得名稱清單: {e}")
        return {}

def get_stock_history_data(stock_id, date_str):
    url = f"https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU?date={date_str}&stockNo={stock_id}&response=json"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code == 200:
            return res.json()
        else:
            return None
    except Exception as e:
        print(f"❌ 網路抓取 {stock_id} 失敗: {e}")
        return None

def write_stock_db(stock_id, date_str, stock_map):
    global conn, cursor
    if not cursor:
        return 0

    json_data = get_stock_history_data(stock_id, date_str)
    
    if not json_data or json_data.get('stat') != 'OK':
        return 0

    stock_name = stock_map.get(stock_id, stock_id)
    raw_datas = json_data['data']
    fields = json_data.get('fields', [])
    
    pe_index = 3
    if '本益比' in fields:
        pe_index = fields.index('本益比')
    
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
        except:
            continue

    sql = "INSERT IGNORE INTO stock_pe_ratio (date, stock_id, stock_name, pe_ratio) VALUES (%s, %s, %s, %s)"
    
    try:
        size = cursor.executemany(sql, clean_data)
        conn.commit()
        return size
    except Exception as e:
        print(f"❌ 寫入錯誤: {e}")
        return 0


# ==========================================
# 3. 專業五階段估值河流圖模組 (參數化)
# ==========================================
# ⚠️ 注意：所有 import 已經全部移到檔案最上方，保持乾淨。

def plot_stock_pe_trend(stock_id, 
                         start_date='2006-01-01', 
                         end_date='2027-12-31',
                         smooth_days=5,
                         std_high=1.5,
                         std_mid=0.5,
                         dpi=300):
    """
    【終極參數化通用函式】
    """
    
    df=get_stock_data(stock_id)

    if df.empty:
        print(f"查無 {stock_id} 的數據，請確認資料庫中是否有資料。")
        return

    stock_name = df['stock_name'].iloc[0] if df['stock_name'].iloc[0] else stock_id
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date']).sort_values('date')
    df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]
    df['pe_ratio'] = pd.to_numeric(df['pe_ratio'], errors='coerce')
    df = df.dropna(subset=['pe_ratio']).set_index('date')

    df['pe_smooth'] = df['pe_ratio'].rolling(window=smooth_days, min_periods=1).mean()

    avg_pe = df['pe_ratio'].mean()
    std_pe = df['pe_ratio'].std()
    
    lv = {
        '極高 (瘋狂)': avg_pe + std_high * std_pe,
        '偏高 (警戒)': avg_pe + std_mid * std_pe,
        '合理 (中性)': avg_pe,
        '偏低 (機會)': avg_pe - std_mid * std_pe,
        '極低 (低估)': avg_pe - std_high * std_pe
    }

    fig, ax = plt.subplots(figsize=(22, 11), facecolor='#FCFCFC')
    ax.set_facecolor('#FCFCFC')

    ax.fill_between(df.index, lv['極高 (瘋狂)'], ax.get_ylim()[1] if ax.get_ylim()[1] > lv['極高 (瘋狂)'] else lv['極高 (瘋狂)']*1.2, color='#FF595E', alpha=0.3, label='極高區 (過熱)')
    ax.fill_between(df.index, lv['偏高 (警戒)'], lv['極高 (瘋狂)'], color='#FFCA3A', alpha=0.2, label='偏高區 (減碼)')
    ax.fill_between(df.index, lv['偏低 (機會)'], lv['偏高 (警戒)'], color='#F8FFE5', alpha=0.2, label='合理區 (持有)')
    ax.fill_between(df.index, lv['極低 (低估)'], lv['偏低 (機會)'], color='#8AC926', alpha=0.2, label='偏低區 (加碼)')
    ax.fill_between(df.index, 0, lv['極低 (低估)'], color='#1982C4', alpha=0.15, label='極低區 (價值)')

    ax.plot(df.index, df['pe_smooth'], color='#1D3557', linewidth=2.5, zorder=5, label=f'{stock_id} PE 走勢')

    max_val, max_dt = df['pe_ratio'].max(), df['pe_ratio'].idxmax()
    min_val, min_dt = df['pe_ratio'].min(), df['pe_ratio'].idxmin()

    ax.scatter([max_dt, min_dt], [max_val, min_val], color=['#D90429', '#023E8A'], s=150, zorder=10, edgecolor='white')
    ax.annotate(f'歷史天花板：{max_val:.2f}', xy=(max_dt, max_val), xytext=(0, 25), textcoords='offset points', ha='center', fontsize=12, fontweight='bold', bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#D90429", alpha=0.9))
    ax.annotate(f'歷史地板：{min_val:.2f}', xy=(min_dt, min_val), xytext=(0, -35), textcoords='offset points', ha='center', fontsize=12, fontweight='bold', bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#023E8A", alpha=0.9))

    latest_pe = df['pe_ratio'].iloc[-1]
    latest_dt = df.index[-1]
    margin = ((latest_pe - avg_pe) / avg_pe) * 100
    box_color = '#FF595E' if latest_pe > lv['偏高 (警戒)'] else '#8AC926' if latest_pe < lv['偏低 (機會)'] else '#FFCA3A'

    ax.annotate(f'【最新數據】\n代號：{stock_id}\n當前 PE：{latest_pe:.2f}\n距均線：{margin:+.2f}%\n日期：{latest_dt.date()}', xy=(latest_dt, latest_pe), xytext=(-220, 80), textcoords='offset points', fontsize=15, fontweight='bold', color='white', bbox=dict(boxstyle="round,pad=0.8", fc=box_color, ec="none"), arrowprops=dict(arrowstyle="fancy", connectionstyle="arc3,rad=.3", color="black"))

    # ⚠️ 將 emoji 移除，防止 Microsoft JhengHei 報錯
    table_data = [
        ["極高階段", f"{lv['極高 (瘋狂)']:.2f} ↑", "分段獲利了結"],
        ["偏高階段", f"{lv['合理 (中性)']:.2f} - {lv['極高 (瘋狂)']:.2f}", "停止追高/減碼"],
        ["合理階段", f"{lv['偏低 (機會)']:.2f} - {lv['合理 (中性)']:.2f}", "持股續抱"],
        ["偏低階段", f"{lv['極低 (低估)']:.2f} - {lv['偏低 (機會)']:.2f}", "建立基本持股"],
        ["極低階段", f"{lv['極低 (低估)']:.2f} ↓", "全力分批佈局"]
    ]
    the_table = plt.table(cellText=table_data, colLabels=["估值階段", "門檻", "建議"], loc='lower right', cellLoc='center', bbox=[0.68, 0.05, 0.30, 0.20])
    the_table.auto_set_font_size(False)
    the_table.set_fontsize(12)
    for key, cell in the_table.get_celld().items():
        cell.set_linewidth(0.5)
        if key[0] == 0: cell.set_facecolor('#1D3557'); cell.set_text_props(weight='bold', color='white')

    ax.set_title(f'{stock_name} ({stock_id}) 歷史五階段估值Rivers圖', fontsize=28, fontweight='bold', pad=35)
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    ax.grid(True, linestyle='--', alpha=0.3)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    plt.tight_layout()

    filename = f"{stock_id}_Ultimate_RiverMap.png"
    plt.savefig(filename, dpi=dpi, bbox_inches='tight')
    
    # ⚠️ 這是最重要的防 Flask 當機機制：存檔後徹底關閉並釋放記憶體
    plt.close(fig) 
    print(f"✅ 圖表已儲存並釋放記憶體：{filename}")
    

# ==========================================
# 4. 主程式入口 (控制台)
# ==========================================
if __name__=="__main__":
    
    TARGET_ID = "2454"                
    FETCH_START = '2006-01-01'        
    
    CHART_START = '2006-01-01'        
    SMOOTH_VAL = 5                    
    STD_H = 1.5                       
    STD_M = 0.5                       
    IMAGE_DPI = 1000                  

    open_db()
    
    if cursor:
        stock_map = get_stock_map()

        date_range = pd.date_range(start=FETCH_START, end=pd.Timestamp.today().strftime('%Y-%m-%d'), freq='MS')
        dates = [d.strftime('%Y%m%d') for d in date_range]

        print(f"\n🚀 開始執行 {TARGET_ID} 歷史數據補完計畫...")
        print(f"📅 預計處理月份總數: {len(dates)}")
        print("-" * 50)

        total_new_records = 0
        for d in dates:
            count = write_stock_db(TARGET_ID, d, stock_map)
            total_new_records += count
            print(f"📅 日期 {d} | 成功寫入: {count} 筆")
            time.sleep(5) 

        print("-" * 50)
        print(f"🏁 爬蟲任務完成！本次累計新增 {total_new_records} 筆資料。")
        
        print(f"📊 正在生成專業圖表...")
        plot_stock_pe_trend(TARGET_ID, 
                            start_date=CHART_START, 
                            smooth_days=SMOOTH_VAL, 
                            std_high=STD_H, 
                            std_mid=STD_M, 
                            dpi=IMAGE_DPI)
        
        close_db()
    else:
        print("🚫 無法建立資料庫連線，請檢查網路或 Aiven 設定。")