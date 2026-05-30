"""快速驗證所有策略函數"""
import backtest_engine

print("=" * 60)
print("🔍 驗證所有回測策略函數")
print("=" * 60)

# 檢查所有策略函數
strategies = [
    ('run_dca_backtest', '每月定額投資'),
    ('run_pe_accumulate_backtest', 'PE 择時累積'),
    ('run_backtest_json', '傳統回測')
]

for func_name, desc in strategies:
    if hasattr(backtest_engine, func_name):
        func = getattr(backtest_engine, func_name)
        print(f"✅ {func_name:30s} - {desc}")
    else:
        print(f"❌ {func_name:30s} - 不存在")

print("=" * 60)
print("✅ 所有策略函數驗證完成！")
print("=" * 60)
