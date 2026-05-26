from app import create_app, db
from app.models import WatchlistItem
import stock_PE

app = create_app()

with app.app_context():
    items = WatchlistItem.query.all()
    print(f'Total watchlist items: {len(items)}')
    
    updated = 0
    for item in items:
        if not item.stock_name or item.stock_name == item.stock_code:
            # 從資料庫取得股票名稱
            df = stock_PE.get_stock_data(item.stock_code)
            if df is not None and not df.empty and 'stock_name' in df.columns:
                new_name = str(df.iloc[-1]['stock_name'])
                if new_name and new_name != item.stock_code:
                    item.stock_name = new_name
                    updated += 1
                    print(f'✅ {item.stock_code}: "{item.stock_code}" -> "{new_name}"')
                else:
                    print(f'⚠️ {item.stock_code}: No name found')
            else:
                print(f'❌ {item.stock_code}: Error reading data')
    
    db.session.commit()
    print(f'\n✅ Updated {updated} items')
