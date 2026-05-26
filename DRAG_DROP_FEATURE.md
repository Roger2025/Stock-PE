# 自選股拖放排序功能

## ✅ 已完成功能

### 1. 資料庫變更
- 在 `watchlist_items` 表添加 `order_index` 欄位（INTEGER 類型）
- 現有記錄已自動設置順序值

### 2. 後端 API
- **修改路由**: `/watchlist` (GET)
  - 改為按 `order_index` 排序而非 `created_at`
  
- **新增路由**: `/watchlist/reorder` (POST)
  - 接收 JSON 格式: `{"stock_codes": ["2330", "2454", "1215"]}`
  - 更新每隻股票的 `order_index` 值
  - 返回: `{"success": true}` 或 `{"success": false, "error": "錯誤訊息"}`

### 3. 前端介面
- **視覺提示**: 
  - 每張卡片左上角顯示拖放圖標（⠿）
  - 滑鼠懸停時顯示 `grab` 光標
  
- **拖放效果**:
  - 拖放中: 卡片半透明 + 旋轉 + 放大
  - 放置目標: 藍色邊框高亮
  - 平滑過渡動畫
  
- **使用者回饋**:
  - 右上角彈出通知: "✅ 排序已更新"
  - 3秒後自動消失

## 📝 使用方法

1. **開始拖放**: 將滑鼠移到卡片左上角的拖放圖標
2. **拖曳**: 按住滑鼠左鍵拖動到其他卡片位置
3. **放置**: 釋放滑鼠左鍵
4. **完成**: 系統自動保存新順序

## 🔧 技術細節

### 新增/修改檔案
```
app/models.py                          - 添加 order_index 欄位
app/routes/watchlist.py                - 添加 reorder 路由 + 修改排序邏輯
templates/watchlist.html               - 添加拖放 CSS + JavaScript
migrate_add_order.py                   - 資料庫遷移腳本
```

### CSS 樣式
```css
.dragging        - 拖放中的樣式（半透明、旋轉）
.drag-over       - 放置目標高亮
.drag-handle     - 拖放圖標樣式
```

### JavaScript 功能
- HTML5 Drag & Drop API
- AJAX 請求更新資料庫
- 動畫通知提示
- 自動重新排序 DOM

## 🎯 優勢

✅ **直觀操作**: 直接拖放卡片改變順序  
✅ **即時反饋**: 視覺效果 + 通知提示  
✅ **自動保存**: 放置後立即更新資料庫  
✅ **使用者友好**: 無需點擊按鈕，自然操作  
✅ **響應式設計**: 支援各種螢幕尺寸  

## 📊 資料庫結構

```sql
watchlist_items:
- id (INT, PRIMARY KEY)
- user_id (INT, FOREIGN KEY)
- stock_code (VARCHAR)
- stock_name (VARCHAR)
- order_index (INT) ← 新增
- created_at (DATETIME)
- updated_at (DATETIME)
```

## 🚀 擴充潛力

未來可添加：
- 排序動畫緩衝效果
- 拖放置頂/置底功能
- 批量移動多張卡片
- 排序歷史記錄
