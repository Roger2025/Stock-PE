"""快速測試 PE 择時累積策略"""
import sys
sys.path.insert(0, '.')

import backtest_engine

print("=" * 70)
print("🧪 測試 PE 择時累積策略")
print("=" * 70)

try:
    result = backtest_engine.run_pe_accumulate_backtest(
        ticker="2330.TW",
        start_date="2020-01-01",
        end_date="2026-05-28",
        monthly_accumulate=5000,
        invest_on_pe_threshold=15
    )
    
    if result['status'] == 'success':
        print("\n✅ 回測成功！\n")
        kpi = result['kpi_cards']
        print(f"📈 股票: {result['ticker']} ({result['start_date']} ~ {result['end_date']})")
        print(f"💰 每月累積: NT${result['monthly_accumulate']:,}")
        print(f"📊 PE 門檻: {result['pe_threshold']}")
        print("-" * 70)
        print("📊 關鍵指標:")
        print(f"  總投入金額:    NT${kpi['total_invested']:>12,.2f}")
        print(f"  最終價值:      NT${kpi['final_value']:>12,.2f}")
        print(f"  總獲利:        NT${kpi['total_profit']:>12,.2f}")
        print(f"  總報酬率:      {kpi['total_return_pct']:>11.2f}%")
        print(f"  年化報酬率:    {kpi['cagr']:>11.2f}%")
        print(f"  最大回撤:      {kpi['max_drawdown']:>11.2f}%")
        print(f"  波動率:        {kpi['volatility']:>11.2f}%")
        print(f"  夏普比率:      {kpi['sharpe_ratio']:>11.2f}")
        print(f"  勝率:          {kpi['win_rate']:>11.1f}%")
        print(f"  投資次數:      {kpi['invest_count']:>12d} 次")
        print("-" * 70)
        print("📝 最近 5 筆投資記錄:")
        for inv in result['trade_results'][-5:]:
            print(f"  {inv['date']}: 投入 NT${inv['amount']:>10,.2f}, 報酬 {inv['return_pct']:>7.2f}%")
        print("=" * 70)
    else:
        print(f"\n❌ 回測失敗: {result['message']}")
except Exception as e:
    print(f"\n❌ 執行錯誤: {e}")
    import traceback
    traceback.print_exc()
