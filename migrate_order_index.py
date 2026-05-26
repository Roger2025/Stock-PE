from app import create_app, db
from app.models import WatchlistItem

app = create_app()

with app.app_context():
    # 為所有現有自選股添加 order_index
    items = WatchlistItem.query.all()
    
    for index, item in enumerate(items):
        item.order_index = index
    
    db.session.commit()
    print(f'✅ 已為 {len(items)} 隻股票設置 order_index')
