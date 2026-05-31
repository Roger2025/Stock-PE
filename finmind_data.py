"""
FinMind 資料庫模組
用於獲取台灣股票數據
"""
import os
import requests
from datetime import datetime
import pandas as pd


class FinMindClient:
    """FinMind API 客戶端"""
    
    def __init__(self):
        # 從環境變數獲取 API Token（推薦方式）
        self.api_token = os.getenv('FINLION_API_TOKEN', '')
        self.base_url = "https://data-api.finmind.com/api"
        
    def test_connection(self):
        """測試連線是否正常"""
        try:
            response = self.datastore(
                dataset="TaiwanStockPrice",
                data_id="2330",
                start_date="2023-01-01",
                end_date="2023-01-31"
            )
            return response is not None and len(response) > 0
        except Exception as e:
            print(f"FinMind 連線測試失敗: {e}")
            return False
    
    def datastore(self, dataset: str, data_id: str = None, 
                  start_date: str = None, end_date: str = None):
        """
        獲取 FinMind 數據
        
        Args:
            dataset: 資料集名稱（如 "TaiwanStockPrice", "TaiwanStockPE"）
            data_id: 股票代號（如 "2330"）
            start_date: 開始日期（格式：YYYY-MM-DD）
            end_date: 結束日期（格式：YYYY-MM-DD）
        
        Returns:
            DataFrame: 數據表格
        """
        params = {
            "dataset": dataset,
            "token": self.api_token,
        }
        
        if data_id:
            params["data_id"] = data_id
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        
        try:
            response = requests.get(
                f"{self.base_url}/datastore",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("error") == 0 and "dataset" in data:
                return pd.DataFrame(data["dataset"])
            else:
                print(f"FinMind API 錯誤: {data}")
                return pd.DataFrame()
        except Exception as e:
            print(f"FinMind 請求失敗: {e}")
            return pd.DataFrame()
    
    def get_stock_price(self, stock_id: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        獲取股票價格數據
        
        Args:
            stock_id: 股票代號（如 "2330"）
            start_date: 開始日期（格式：YYYY-MM-DD）
            end_date: 結束日期（格式：YYYY-MM-DD）
        
        Returns:
            DataFrame: 包含日期、收盤價等數據
        """
        df = self.datastore(
            dataset="TaiwanStockPrice",
            data_id=stock_id,
            start_date=start_date,
            end_date=end_date
        )
        
        if df.empty:
            return df
        
        # 欄位映射（FinMind → yfinance 格式）
        # Trading_Date → Date
        # Close → Close
        # Adj_Close → Adj Close
        mapping = {}
        if 'Trading_Date' in df.columns:
            mapping['Trading_Date'] = 'date'
        if 'Close' in df.columns:
            mapping['Close'] = 'close'
        if 'Adj_Close' in df.columns:
            mapping['Adj_Close'] = 'adj_close'
        if 'Volume' in df.columns:
            mapping['Volume'] = 'volume'
        if 'Open' in df.columns:
            mapping['Open'] = 'open'
        if 'High' in df.columns:
            mapping['High'] = 'high'
        if 'Low' in df.columns:
            mapping['Low'] = 'low'
        
        # 重新命名欄位
        df = df.rename(columns=mapping)
        
        # 確保必要的欄位存在
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date')
            df = df.sort_index()
        
        return df
    
    def get_stock_pe(self, stock_id: str, date: str = None) -> float:
        """
        獲取股票 PE 比率
        
        Args:
            stock_id: 股票代號（如 "2330"）
            date: 日期（格式：YYYY-MM-DD），如果不提供則獲取最新 PE
        
        Returns:
            float: PE 比率，如果找不到則返回 None
        """
        dataset = "TaiwanStockPE"
        
        # 如果有指定日期，獲取該日期的 PE
        if date:
            # FinMind 的 PE 數據是按財報期間的，需要獲取該日期前最近的財報
            df = self.datastore(
                dataset=dataset,
                data_id=stock_id,
                start_date="2000-01-01",
                end_date=date
            )
        else:
            df = self.datastore(
                dataset=dataset,
                data_id=stock_id
            )
        
        if df.empty:
            return None
        
        # 獲取最新的 PE
        if 'PE' in df.columns:
            # 過濾有效的 PE 值
            valid_pe = df[df['PE'] > 0]
            if not valid_pe.empty:
                return float(valid_pe.iloc[-1]['PE'])
        
        return None
    
    def get_stock_list(self) -> pd.DataFrame:
        """
        獲取所有台灣股票列表
        
        Returns:
            DataFrame: 股票列表
        """
        return self.datastore(dataset="TaiwanStock")
    
    def get_financial_statement(self, stock_id: str, 
                               financial_type: str = "year") -> pd.DataFrame:
        """
        獲取財務報表
        
        Args:
            stock_id: 股票代號
            financial_type: 財報類型 ("year"=年度, "quarter"=季度)
        
        Returns:
            DataFrame: 財務報表數據
        """
        dataset = "TaiwanStockFinancialStatement_AID" if financial_type == "year" else "TaiwanStockFinancialStatement_AID"
        return self.datastore(dataset=dataset, data_id=stock_id)


# 全域實例
finmind_client = FinMindClient()


def get_stock_from_finmind(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    從 FinMind 獲取股票數據（兼容 yfinance 格式）
    
    Args:
        symbol: 股票代號（如 "2330.TW" 或 "2330"）
        start_date: 開始日期（格式：YYYY-MM-DD）
        end_date: 結束日期（格式：YYYY-MM-DD）
    
    Returns:
        DataFrame: 包含 Close 和 Adj Close 欄位的數據
    """
    # 移除 .TW 後綴
    stock_id = symbol.replace('.TW', '')
    
    # 獲取數據
    df = finmind_client.get_stock_price(stock_id, start_date, end_date)
    
    if df.empty:
        raise ValueError(f"無法從 FinMind 獲取 {stock_id} 在 {start_date} 至 {end_date} 的數據")
    
    # 確保有必要的欄位
    result = pd.DataFrame(index=df.index)
    
    if 'close' in df.columns:
        result['Close'] = df['close']
    
    if 'adj_close' in df.columns:
        result['Adj Close'] = df['adj_close']
    elif 'close' in df.columns:
        # 如果沒有 Adj Close，使用 Close
        result['Adj Close'] = df['close']
    
    # 移除 NaN 值
    result = result.dropna()
    
    return result


def get_pe_from_finmind(stock_id: str, date: str = None) -> float:
    """
    從 FinMind 獲取 PE 比率
    
    Args:
        stock_id: 股票代號
        date: 日期（格式：YYYY-MM-DD）
    
    Returns:
        float: PE 比率
    """
    return finmind_client.get_stock_pe(stock_id, date)


if __name__ == "__main__":
    # 測試程式
    print("FinMind 模組測試")
    print("=" * 50)
    
    # 測試連線
    client = FinMindClient()
    
    if client.test_connection():
        print("✅ FinMind 連線成功！")
    else:
        print("❌ FinMind 連線失敗，請檢查 API Token")
        print("請設定環境變數: FINLION_API_TOKEN=your_token")
    
    # 測試獲取數據
    print("\n測試獲取台積電股價...")
    df = get_stock_from_finmind("2330", "2024-01-01", "2024-01-31")
    print(df.head())
