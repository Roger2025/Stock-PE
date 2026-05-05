import os
import logging
from pathlib import Path

import pandas as pd
import markdown
from flask import Flask, render_template, request, url_for
from openai import OpenAI, OpenAIError
from dotenv import load_dotenv

import stock_PE

# ==========================================
# 專業設定 1：初始化系統日誌 (Logging)
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ==========================================
# 專業設定 2：環境與核心服務實例化
# ==========================================
load_dotenv()
app = Flask(__name__)

# 確保從環境變數正確抓取 API Key
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

# 使用現代化 Pathlib 建立與管理靜態目錄
STATIC_IMG_DIR = Path(app.root_path) / "static" / "images"
STATIC_IMG_DIR.mkdir(parents=True, exist_ok=True)


# ==========================================
# 核心服務：AI 報告生成器
# ==========================================
def generate_ai_report(stock_id: str, df: pd.DataFrame) -> str:
    """
    將 DataFrame 轉換為文字，並呼叫 OpenAI 生成 HTML 格式的報告。
    """
    try:
        if df is None or df.empty:
            logger.warning(f"[{stock_id}] 資料庫無數據，取消 AI 生成。")
            return "<p style='color:#E63946;'><strong>⚠️ 無法取得資料庫數據，無法生成 AI 報告。</strong></p>"

        # --- 型別修正與髒數據清洗 ---
        df = df.copy() 
        # 1. 加入 errors='coerce'，遇到 0000-00-00 就強制作為 NaT (空值)
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        # 2. 把變成空值的無效資料刪除，確保接下來排隊的都是正確日期
        df = df.dropna(subset=['date'])
        
        # 準備數據：排序並取最後 20 筆
        df_sorted = df.sort_values('date')
        report_data = df_sorted.tail(20).to_string()

        # 呼叫 GPT 進行分析
        logger.info(f"[{stock_id}] 正在發送請求至 OpenAI API...")
        
        # 增加 timeout 到 45 秒，避免 Render 連線過慢超時
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system", 
                    "content": "你是一位精通台股的價值投資分析師。請根據提供的本益比歷史數據，判斷目前估值處於什麼位階，並給出專業、簡潔的投資與操盤建議。請務必使用 Markdown 格式排版。"
                },
                {
                    "role": "user", 
                    "content": f"這是代號 {stock_id} 最新 20 天的數據：\n{report_data}\n請給出分析報告。"
                }
            ],
            timeout=45 
        )
        
        logger.info(f"[{stock_id}] OpenAI 報告生成完畢。")
        ai_markdown = response.choices[0].message.content
        return markdown.markdown(ai_markdown)

    except OpenAIError as api_err:
        logger.error(f"[{stock_id}] OpenAI API 發生錯誤：{api_err}")
        return f"<p style='color:#E63946;'><strong>⚠️ AI 服務暫時無法使用，請檢查 API Key 或餘額。</strong></p>"
    except Exception as e:
        logger.exception(f"[{stock_id}] 報告生成發生錯誤")
        return f"<p style='color:#E63946;'><strong>⚠️ 系統分析出錯：{str(e)}</strong></p>"


# ==========================================
# Web 路由設計 (Routing)
# ==========================================
@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')


@app.route('/analyze', methods=['POST'])
def analyze():
    stock_id = request.form.get('stock_id', '').strip()
    
    if not stock_id:
        return "❌ 錯誤：請輸入股票代號！", 400

    try:
        logger.info(f"========== 開始處理股票分析：{stock_id} ==========")

        # --- 步驟 A：產出河流圖 (DPI 調低至 100 以節省記憶體) ---
        logger.info(f"[{stock_id}] 正在生成河流圖...")
        stock_PE.plot_stock_pe_trend(
            stock_id=stock_id, 
            start_date='2006-01-01', 
            smooth_days=5, 
            dpi=100
        )

        # --- 步驟 B：靜態資源歸檔 (搬移圖片) ---
        original_image = Path(f"{stock_id}_Ultimate_RiverMap.png")
        target_image_path = STATIC_IMG_DIR / original_image.name
        
        if original_image.exists():
            # 先移除舊圖，再移動新圖，避免 replace 在某些系統報錯
            if target_image_path.exists():
                target_image_path.unlink()
            original_image.replace(target_image_path)
            logger.info(f"[{stock_id}] 圖片已歸檔。")
        else:
            logger.warning(f"[{stock_id}] 未找到產出的圖檔。")

        final_image_url = url_for('static', filename=f'images/{original_image.name}')

        # --- 步驟 C：撈取數據與 AI 報告 ---
        df = stock_PE.get_stock_data(stock_id)
        ai_html_report = generate_ai_report(stock_id, df)

        logger.info(f"========== {stock_id} 處理完成 ==========")
        return render_template(
            'result.html', 
            stock_id=stock_id, 
            image_url=final_image_url, 
            ai_report=ai_html_report
        )

    except Exception as e:
        logger.exception(f"處理時發生致命錯誤: {stock_id}")
        return f"❌ 伺服器處理失敗: {str(e)}", 500


if __name__ == "__main__":
    # 本地開發時使用，部署到 Render 時會由 Gunicorn 接管
    logger.info("啟動 Flask 伺服器...")
    app.run(host='0.0.0.0', port=5000)