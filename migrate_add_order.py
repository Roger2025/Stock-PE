from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    # 添加 order_index 欄位
    try:
        db.session.execute(text("ALTER TABLE watchlist_items ADD COLUMN order_index INT DEFAULT 0 AFTER stock_name"))
        print("✅ Added order_index column")
    except Exception as e:
        if "Duplicate column name" in str(e):
            print("✅ order_index column already exists")
        else:
            db.session.rollback()
            print(f"Error: {e}")
            raise
    
    # 為現有記錄設置 order_index
    db.session.execute(text("SET @row_number = 0"))
    db.session.execute(text("UPDATE watchlist_items SET order_index = (@row_number:=@row_number+1) WHERE user_id = (SELECT id FROM users ORDER BY id LIMIT 1)"))
    db.session.commit()
    print("✅ Set order_index for existing records")
