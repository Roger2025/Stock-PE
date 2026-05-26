from app import create_app, db

app = create_app()

with app.app_context():
    # 使用原生 SQL 添加 order_index 欄位
    sql = """
    ALTER TABLE watchlist_items 
    ADD COLUMN order_index INT DEFAULT 0 AFTER stock_name
    """
    try:
        db.engine.execute(sql)
        print('✅ 已成功添加 order_index 欄位')
        
        # 為現有記錄設置 order_index
        sql2 = """
        SET @row_number = 0;
        UPDATE watchlist_items 
        SET order_index = (@row_number:=@row_number+1)
        """
        db.engine.execute(sql2)
        print('✅ 已為現有記錄設置 order_index')
        
    except Exception as e:
        print(f'⚠️ 錯誤: {e}')
        print('如果錯誤是 "Duplicate column name"，表示欄位已存在')
