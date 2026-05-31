from app import create_app
from app.models import User, WatchlistItem

app = create_app()

with app.app_context():
    print('=== All Users ===')
    users = User.query.all()
    print(f'Total: {len(users)}')
    for u in users:
        print(f'  - {u.email} | VIP: {u.is_vip} | ID: {u.id}')
    
    print('\n=== Check VIP with Watchlists ===')
    vip_users = User.query.filter_by(is_vip=True).all()
    print(f'VIP count: {len(vip_users)}')
    for u in vip_users:
        watchlist = WatchlistItem.query.filter_by(user_id=u.id).all()
        print(f'  - {u.email} has {len(watchlist)} watchlist items')
        for item in watchlist:
            print(f'      {item.stock_code} - {item.stock_name}')
