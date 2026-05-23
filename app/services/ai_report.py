# ==========================================
# AI 報告生成服務
# ==========================================
import pandas as pd
import markdown
from openai import OpenAI, OpenAIError
from config import Config

# 初始化 OpenAI 客戶端
client = OpenAI(api_key=Config.OPENAI_API_KEY)


def generate_ai_report(stock_id: str, df: pd.DataFrame) -> str:
    """
    生成 AI 投資診斷報告
    
    Args:
        stock_id: 股票代號
        df: 股票數據 DataFrame
    
    Returns:
        Markdown 格式的 HTML 報告
    """
    try:
        if df is None or df.empty:
            return "<p style='color:#E63946;'><strong>⚠️ 無法取得資料庫數據。</strong></p>"
        
        # 強制清洗數據流
        df_clean = df.copy()
        for col in df_clean.select_dtypes(include=['float64', 'float32']).columns:
            df_clean[col] = df_clean[col].round(2)
        
        df_clean['date'] = df_clean['date'].astype(str)
        df_sorted = df_clean.sort_values('date')
        report_data = df_sorted.tail(20).to_string()
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "你是一位精通台股的價值投資分析師。請使用 Markdown 格式。"},
                {"role": "user", "content": f"分析代號 {stock_id} 最新數據：\n{report_data}"}
            ],
            timeout=45
        )
        return markdown.markdown(response.choices[0].message.content)
    
    except Exception as e:
        return f"<p style='color:#E63946;'><strong>⚠️ AI 分析出錯：{str(e)}</strong></p>"
