# FinMind 資料庫接入說明

## 📋 安裝步驟

### 1. 獲取 FinMind API Token

1. 前往 [FinMind 開放平台](https://finmind.github.io/)
2. 註冊帳號
3. 獲取 API Token（Free 方案：300 次/小時）

### 2. 設定環境變數

在 `.env` 檔案中加入：

```env
# 資料來源設定（yfinance 或 finmind）
DATA_SOURCE=finmind

# FinMind API Token
FINLION_API_TOKEN=your_token_here
```

### 3. 安裝依賴

```bash
pip install requests
```

## 🔄 切換資料來源

### 使用 yfinance（預設）
```env
DATA_SOURCE=yfinance
```

### 使用 FinMind
```env
DATA_SOURCE=finmind
FINLION_API_TOKEN=your_token_here
```

## 📊 FinMind 資料集對照

| 資料用途 | FinMind 資料集 | 說明 |
|---------|---------------|------|
| 股價數據 | TaiwanStockPrice | 開盤價、收盤價、成交量等 |
| PE 比率 | TaiwanStockPE | 本益比 |
| PBR 比率 | TaiwanStockPBR | 市淨比 |
| 財務報表 | TaiwanStockFinancialStatement_AID | 財務報表 |
| 股務資訊 | TaiwanStockOwnership | 股東結構 |

## 🧪 測試 FinMind 連線

```bash
python finmind_data.py
```

如果看到以下輸出表示連線成功：
```
FinMind 模組測試
==================================================
✅ FinMind 連線成功！
```

## ⚠️ 注意事項

1. **Free 方案限制**：300 次/小時
   - 建議不要頻繁呼叫
   - 可以加入緩存機制

2. **資料格式差異**
   - FinMind 的日期格式是 `Trading_Date`
   - 本系統已自動轉換為 yfinance 格式

3. **錯誤處理**
   - 如果 FinMind 連線失敗，系統會自動切換回 yfinance
   - 不會影響系統正常運作

## 🚀 優勢

### 使用 FinMind 的好處：
- ✅ 資料更準確（台灣官方數據）
- ✅ 不需要處理 yfinance 的連線問題
- ✅ 提供更多資料集（財務、股務、選擇權等）
- ✅ API 穩定性高

### 使用 yfinance 的好處：
- ✅ 不需要 API Token
- ✅ 免費無限制
- ✅ 國際股票數據豐富
- ✅ 設定簡單

## 📞 問題排除

### Q: 連線失敗怎麼辦？
A: 檢查以下項目：
1. API Token 是否正確
2. 網路是否正常
3. 是否超過 API 呼叫限制

### Q: 可以同時使用兩個資料源嗎？
A: 可以！系統會根據 `DATA_SOURCE` 設定自動切換

### Q: 如果 FinMind 沒有某支股票怎麼辦？
A: 系統會自動切換回 yfinance 獲取數據
