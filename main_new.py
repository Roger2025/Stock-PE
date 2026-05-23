# ==========================================
# Roger Quant - 啟動入口
# ==========================================
import os
import sys

try:
    print("🚀 正在導入 Flask 應用...")
    from app import create_app
    print("✅ 導入成功")
    
    print("🚀 正在創建應用...")
    app = create_app()
    print("✅ 應用創建成功")

except Exception as e:
    print(f"❌ 錯誤：{e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

if __name__ == "__main__":
    print("🚀 Roger Quant SaaS 正在啟動...")
    print("📍 訪問地址: http://127.0.0.1:10000")
    app.run(host='0.0.0.0', port=10000, debug=True)
