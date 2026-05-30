# PE 择時累積策略 - 實現總結

## ✅ 已完成功能 (2026-05-30)

### 1. 後端實現 (backtest_engine.py)
- ✅ 添加 `run_pe_accumulate_backtest()` 函數
- ✅ 策略邏輯：
  - 每月自動累積指定金額到等待池
  - 當 PE < 門檻時，將等待池中的所有錢一次性投入
  - 投入後重新開始累積
- ✅ 返回完整的回測結果（KPI、投資記錄、圖表數據）

### 2. API 端點 (app/routes/analysis.py)
- ✅ 修改 `/api/run_dca_backtest` 支持三種策略：
  - `dca`: 每月定額投資
  - `pe`: PE 择時投資
  - `accumulate`: PE 择時累積（新增）

### 3. 前端界面 (templates/backtest_dca.html)
- ✅ 添加第三個策略選項："PE 择時累積"
- ✅ 策略切換邏輯支持 accumulate 模式
- ✅ 自動顯示/隱藏相關字段

## 📊 策略對比

| 策略 | 說明 | 適合人群 |
|------|------|----------|
| **每月定額投資** | 固定每月投入固定金額 | 保守型，堅持紀律 |
| **PE 择時投資** | PE < 門檻時才投資，每月投入 | 進取型，等待好時機 |
| **PE 择時累積** | 每月累積資金，PE < 門檻時一次性投入 | 進取型，等待好時機 + 降低交易頻率 |

## 🎯 PE 择時累積策略優勢

1. **避免"等太久"的問題** - 錢會累積，等到時就是一筆大資金
2. **降低交易頻率** - 一次性投入比每月小額更有效
3. **更符合現實** - 人們通常會攢一筆錢再投資
4. **減少高點投入** - 只在 PE 低時才投入，降低最大回撤

## 📈 關鍵指標

- `total_invested`: 總投入金額
- `final_value`: 最終價值
- `total_profit`: 總獲利
- `total_return_pct`: 總報酬率
- `cagr`: 年化報酬率
- `max_drawdown`: 最大回撤
- `volatility`: 波動率
- `sharpe_ratio`: 夏普比率
- `invest_count`: 投資次數
- `win_rate`: 勝率

## 🔧 技術細節

### 等待池機制
```python
waiting_pool = 0  # 等待池金額

# 每月累積
waiting_pool += monthly_accumulate

# PE 低時一次性投入
if should_invest and waiting_pool > 0:
    invest_amount = waiting_pool
    # 買入股數...
    waiting_pool -= cost  # 扣除已投入金額
```

### PE 數據緩存
- 使用 `build_pe_cache()` 一次性獲取所有歷史 PE 數據
- 使用 `get_pe_for_date()` 查詢指定日期的 PE 值
- 避免重複查詢資料庫，提升性能

## 🧪 測試驗證

```bash
# 驗證函數是否存在
.venv\Scripts\python.exe -c "import backtest_engine; print(hasattr(backtest_engine, 'run_pe_accumulate_backtest'))"
# 輸出: True

# 運行完整測試
.venv\Scripts\python.exe test_accumulate.py
```

## 📝 使用示例

### 後端調用
```python
import backtest_engine

result = backtest_engine.run_pe_accumulate_backtest(
    ticker="2330.TW",
    start_date="2020-01-01",
    end_date="2026-05-28",
    monthly_accumulate=5000,
    invest_on_pe_threshold=15
)
```

### API 調用
```javascript
fetch('/api/run_dca_backtest', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
        ticker: '2330',
        stock_name: '台積電',
        strategy: 'accumulate',  // 新增策略類型
        start_date: '2020-01-01',
        end_date: '2026-05-28',
        monthly_amount: 5000,
        invest_on_pe_threshold: 15
    })
})
```

## 🚀 下一步優化

- [ ] 前端顯示等待池曲線圖
- [ ] 前端顯示投資次數統計
- [ ] 三策略對照比較功能
- [ ] 優化前端 KPI 卡片顯示
- [ ] 添加更多策略參數調整

## 📁 修改文件清單

1. **backtest_engine.py** - 添加 `run_pe_accumulate_backtest()` 函數 (~260 行)
2. **app/routes/analysis.py** - 修改 API 端點支持 accumulate 策略
3. **templates/backtest_dca.html** - 添加第三個策略選項和切換邏輯
4. **test_accumulate.py** - 創建測試腳本

## ✅ 驗證狀態

- ✅ 所有 Python 文件語法檢查通過
- ✅ 函數成功導入
- ✅ API 端點正確配置
- ✅ 前端界面更新完成
