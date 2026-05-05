import time
import random
import pandas as pd
import stock_PE  # 引用你寫好的 open_db, write_stock_db 等函式

def run_batch_fetch(max_stocks=50, start_year='2006'):
    """
    批次抓取多檔股票的歷史資料並寫入 Aiven 雲端資料庫
    """
    stock_PE.open_db()
    
    if not stock_PE.cursor:
        print("🚫 連線失敗，請檢查 .env 設定或 Aiven 防火牆。")
        return

    # 1. 取得全市場股票清單
    print("🔍 正在取得全市場股票清單...")
    stock_map = stock_PE.get_stock_map()
    
    if not stock_map:
        print("❌ 無法取得股票清單，程式終止。")
        stock_PE.close_db()
        return

    # 2. 取出前 max_stocks 檔股票 (stock_map 是一個 dict)
    # 這裡會依序取出前 50 檔 (通常從 1101 台泥 開始)
    target_stocks = list(stock_map.keys())[:max_stocks]
    
    print(f"✅ 成功取得清單，本次預計抓取 {len(target_stocks)} 檔股票。")
    print("=" * 50)

    # 建立從開始年份到今天的每個月第一天清單
    start_date = f'{start_year}-01-01'
    date_range = pd.date_range(
        start=start_date, 
        end=pd.Timestamp.today().strftime('%Y-%m-%d'), 
        freq='MS'
    )
    dates = [d.strftime('%Y%m%d') for d in date_range]

    total_all_records = 0
    stock_count = 0

    # 3. 雙層迴圈：外層跑不同股票，內層跑不同月份
    for stock_id in target_stocks:
        stock_name = stock_map[stock_id]
        stock_count += 1
        print(f"\n🚀 [{stock_count}/{len(target_stocks)}] 開始處理【{stock_name} ({stock_id})】...")
        
        total_new_records = 0
        for d in dates:
            # 呼叫 stock_PE 裡的寫入函式
            count = stock_PE.write_stock_db(stock_id, d, stock_map)
            total_new_records += count
            print(f"  📅 月份 {d} | 新增: {count} 筆")
            
            # 【防禦機制 1】隨機小冷卻：月份之間休息 3 到 6 秒
            sleep_time = random.uniform(3, 6)
            time.sleep(sleep_time) 

        total_all_records += total_new_records
        print(f"🏁 【{stock_name} ({stock_id})】補貨完成！共新增 {total_new_records} 筆。")
        
        # 【防禦機制 2】隨機大冷卻：股票之間休息 10 到 20 秒，徹底清除機器人嫌疑
        if stock_count < len(target_stocks):
            big_sleep = random.uniform(10, 20)
            print(f"☕ 準備抓取下一檔，喝口水大休息 {big_sleep:.1f} 秒...\n")
            time.sleep(big_sleep)

    print("=" * 50)
    print(f"🎉 全部任務完成！{stock_count} 檔股票共新增 {total_all_records} 筆資料到 Aiven。")
    stock_PE.close_db()

if __name__ == "__main__":
    # 你想睡覺時抓 50 檔，直接在這裡設定
    run_batch_fetch(max_stocks=50, start_year="2006")