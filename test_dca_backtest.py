"""
定額投資回測功能測試腳本
"""
from backtest_engine import run_dca_backtest
import json

print("=" * 60)
print("🧪 定額投資回測系統測試")
print("=" * 60)

# 測試參數
result = run_dca_backtest(
    ticker="2330.TW",
    start_date="2020-01-01",
    end_date="2025-12-31",
    initial_amount=10000,
    monthly_amount=5000
)

if result['status'] == 'success':
    print("\n✅ 回測執行成功！\n")
    print("📊 回測結果摘要：")
    print(f"   股票代號：{result['ticker']}")
    print(f"   時間範圍：{result['start_date']} ~ {result['end_date']}")
    print(f"   初始投資：${result['initial_amount']:,}")
    print(f"   每月定額：${result['monthly_amount']:,}")
    print(f"   總投入金額：${result['total_invested']:,}")
    print(f"   目前總價值：${result['final_value']:,}")
    print(f"   總報酬金額：${result['total_profit']:,}")
    print(f"   總報酬率：{result['total_return_pct']:.2f}%")
    print(f"   年化報酬率 (CAGR)：{result['cagr']:.2f}%")
    print(f"   最大回撤：{result['max_drawdown']:.2f}%")
    print(f"   年化波動率：{result['volatility']:.2f}%")
    print(f"   夏普比率：{result['sharpe_ratio']:.2f}")
    print(f"   投資月數：{result['invest_months']} 個月")
    print(f"   勝率：{result['win_rate']:.1f}%")
    
    print(f"\n📝 最近投資記錄（最後 5 筆）：")
    for i, inv in enumerate(result['investment_log'][-5:]):
        print(f"   {i+1}. {inv['date']} | 股價: ${inv['price']} | 金額: ${inv['amount']:,} | 股數: {inv['shares']}")
    
    print("\n" + "=" * 60)
    print("✅ 測試完成！功能正常！")
    print("=" * 60)
else:
    print(f"\n❌ 回測失敗：{result['message']}")
