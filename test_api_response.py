import requests
import json

url = 'http://127.0.0.1:10000/api/run_dca_backtest'
payload = {
    'ticker': '2330',
    'start_date': '2020-01-01',
    'end_date': '2026-05-30',
    'initial_amount': 10000,
    'monthly_amount': 5000
}

print("Sending request to API...")
print("NOTE: This API requires login and VIP access!")
print("If not logged in, it will redirect to login page (HTML response)")
print()

r = requests.post(url, json=payload, timeout=60, allow_redirects=False)
print("Response status code:", r.status_code)
print("Response Content-Type:", r.headers.get('Content-Type'))

if r.status_code in [302, 301, 303]:
    print()
    print("⚠️  API returned a redirect (likely to login page)")
    print("Location:", r.headers.get('Location'))
    print()
    print("This means the API requires authentication!")
    print("You need to:")
    print("  1. Login to the application first")
    print("  2. Have VIP status enabled")
    print("  3. Use session/cookies from the login")
elif r.status_code == 200:
    try:
        data = r.json()
        print()
        print("=" * 80)
        print("API Response Structure:")
        print("=" * 80)
        print("Status:", data.get('status'))
        print("Top-level keys:", list(data.keys()))
        print()
        print("Has 'investment_log':", 'investment_log' in data)
        print("Has 'kpi_cards':", 'kpi_cards' in data)
        print("Has 'chart_data':", 'chart_data' in data)
        print()

        if 'investment_log' in data:
            print("investment_log type:", type(data['investment_log']))
            print("investment_log length:", len(data['investment_log']) if data['investment_log'] else 0)
            if data['investment_log'] and len(data['investment_log']) > 0:
                print("First item:", json.dumps(data['investment_log'][0], ensure_ascii=False, indent=2))
        else:
            print("investment_log: NOT FOUND in response!")

        if 'kpi_cards' in data:
            print()
            print("kpi_cards keys:", list(data['kpi_cards'].keys()) if isinstance(data['kpi_cards'], dict) else type(data['kpi_cards']))
        else:
            print("kpi_cards: NOT FOUND in response!")

        if 'chart_data' in data:
            print()
            print("chart_data keys:", list(data['chart_data'].keys()) if isinstance(data['chart_data'], dict) else type(data['chart_data']))
        else:
            print("chart_data: NOT FOUND in response!")

        print("=" * 80)
    except Exception as e:
        print("JSON decode error:", e)
        print("Response is NOT valid JSON!")
        print("First 500 chars:", r.text[:500])
