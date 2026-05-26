import pathlib

new_content = '''<!doctype html>
<html lang="zh-Hant">

<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
  <title>自選股戰情室 | Roger SaaS</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <link rel="stylesheet" href="{{ url_for('static', filename='css/transitions.css') }}?v=1.0">
  <link rel="apple-touch-icon" sizes="512x512"
    href="{{ url_for('static', filename='img/apple-touch-icon.png') }}?v=2.0">
  <style>
    body {
      font-family: "Microsoft JhengHei", "Noto Sans TC", sans-serif;
      background-color: #0a0b14;
      color: #e4e7eb;
      overflow-x: hidden;
      margin: 0;
    }

    .navbar {
      background: rgba(10, 11, 20, 0.9) !important;
      backdrop-filter: blur(10px);
      border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    }

    .navbar-brand {
      letter-spacing: 1px;
      font-weight: 800;
    }

    .btn-upgrade-portal {
      background: linear-gradient(135deg, #f0932b 0%, #ff5e62 100%);
      color: #ffffff !important;
      font-weight: 800;
      border: none;
      padding: 6px 16px;
      border-radius: 50px;
      box-shadow: 0 0 15px rgba(255, 94, 98, 0.4);
      transition: all 0.3s ease;
      letter-spacing: 0.5px;
    }

    .btn-upgrade-portal:hover {
      transform: scale(1.05);
      box-shadow: 0 0 25px rgba(255, 94, 98, 0.7);
      color: #ffffff;
    }

    .btn-admin-portal {
      background: linear-gradient(135deg, #8A2387 0%, #E94057 50%, #F27121 100%);
      color: #ffffff !important;
      font-weight: 800;
      border: none;
      padding: 6px 16px;
      border-radius: 6px;
      box-shadow: 0 0 15px rgba(233, 64, 87, 0.5);
      transition: all 0.3s ease;
      letter-spacing: 0.5px;
    }

    .btn-admin-portal:hover {
      transform: translateY(-2px);
      box-shadow: 0 0 25px rgba(233, 64, 87, 0.8);
      color: #ffffff;
    }

    .hero-section {
      padding: 100px 15px 40px;
      background: radial-gradient(circle at center, rgba(29, 53, 87, 0.5) 0%, rgba(10, 11, 20, 1) 80%);
      text-align: center;
      position: relative;
    }

    .hero-title {
      font-size: 2.8rem;
      font-weight: 800;
      letter-spacing: 2px;
      margin-bottom: 15px;
      background: linear-gradient(135deg, #ffffff 30%, #4facfe 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }

    .hero-subtitle {
      color: #8b9bb4;
      font-size: 1.1rem;
      max-width: 650px;
      margin: 0 auto 35px;
      line-height: 1.6;
    }

    .search-container {
      max-width: 520px;
      width: 100%;
      margin: 0 auto 40px;
      background: #131524;
      padding: 40px 35px;
      border-radius: 16px;
      border: 1px solid rgba(255, 255, 255, 0.1);
      box-shadow: 0 20px 50px rgba(0, 0, 0, 0.6);
      transition: transform 0.3s ease, box-shadow 0.3s ease;
    }

    .search-container:hover {
      transform: translateY(-3px);
      box-shadow: 0 25px 60px rgba(79, 172, 254, 0.15);
      border-color: rgba(79, 172, 254, 0.4);
    }

    .search-container h3 {
      color: #ffffff;
      font-weight: 700;
      margin-bottom: 10px;
      font-size: 1.5rem;
    }

    .search-container p {
      color: #8b9bb4;
      font-size: 0.95rem;
      margin-bottom: 25px;
    }

    input[type="text"] {
      padding: 16px 20px;
      width: 100%;
      font-size: 1rem;
      font-weight: 600;
      background-color: rgba(10, 11, 20, 0.8);
      border: 2px solid rgba(255, 255, 255, 0.15);
      color: #ffffff;
      border-radius: 10px;
      margin-bottom: 20px;
      transition: all 0.3s ease;
    }

    input[type="text"]:focus {
      border-color: #4facfe;
      background-color: #0a0b14;
      outline: none;
      box-shadow: 0 0 15px rgba(79, 172, 254, 0.3);
    }

    input[type="text"]::placeholder {
      color: #5c6a7e;
      font-weight: 400;
    }

    .btn-submit-custom {
      width: 100%;
      padding: 16px;
      font-size: 1.1rem;
      font-weight: 700;
      background: linear-gradient(135deg, #1d3557 0%, #4facfe 100%);
      color: white;
      border: none;
      border-radius: 10px;
      cursor: pointer;
      transition: all 0.3s ease;
      box-shadow: 0 4px 15px rgba(79, 172, 254, 0.3);
    }

    .btn-submit-custom:hover {
      background: linear-gradient(135deg, #4facfe 0%, #1d3557 100%);
      transform: translateY(-2px);
      box-shadow: 0 8px 20px rgba(79, 172, 254, 0.5);
    }

    /* ===== 自選股卡片 ===== */
    .stock-card {
      background: #131524;
      border-radius: 16px;
      border: 1px solid rgba(255, 255, 255, 0.06);
      overflow: hidden;
      transition: all 0.3s ease;
      height: 100%;
      min-height: 280px;
    }

    .stock-card:hover {
      transform: translateY(-6px);
      border-color: rgba(79, 172, 254, 0.35);
      box-shadow: 0 16px 48px rgba(0, 0, 0, 0.5), 0 0 20px rgba(79, 172, 254, 0.08);
    }

    .stock-card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 18px 22px 14px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    }

    .stock-code {
      font-size: 1.35rem;
      font-weight: 800;
      color: #4facfe;
      letter-spacing: 1px;
    }

    .stock-name {
      font-size: 0.82rem;
      color: #8b9bb4;
      margin-top: 2px;
    }

    .btn-remove {
      background: transparent;
      border: none;
      color: #5c6a7e;
      font-size: 1.1rem;
      padding: 6px 10px;
      border-radius: 8px;
      transition: all 0.2s ease;
    }

    .btn-remove:hover {
      color: #ef4444;
      background: rgba(239, 68, 68, 0.1);
    }

    .stock-card-body {
      padding: 20px 22px 24px;
    }

    .pe-display {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      margin-bottom: 14px;
    }

    .pe-label {
      font-size: 0.8rem;
      color: #5c6a7e;
      text-transform: uppercase;
      letter-spacing: 1.5px;
      font-weight: 600;
    }

    .pe-value {
      font-size: 2.2rem;
      font-weight: 800;
      transition: all 0.3s ease;
    }

    .pe-low {
      color: #10b981;
      text-shadow: 0 0 20px rgba(16, 185, 129, 0.3);
    }

    .pe-mid {
      color: #f59e0b;
      text-shadow: 0 0 20px rgba(245, 158, 11, 0.3);
    }

    .pe-high {
      color: #ef4444;
      text-shadow: 0 0 20px rgba(239, 68, 68, 0.3);
    }

    .grade-display {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 14px;
    }

    .grade-badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 36px;
      height: 36px;
      border-radius: 10px;
      font-size: 1.1rem;
      font-weight: 800;
      color: #fff;
    }

    .grade-a { background: linear-gradient(135deg, #10b981, #059669); box-shadow: 0 4px 12px rgba(16, 185, 129, 0.35); }
    .grade-b { background: linear-gradient(135deg, #34d399, #10b981); box-shadow: 0 4px 12px rgba(52, 211, 153, 0.35); }
    .grade-c { background: linear-gradient(135deg, #fbbf24, #f59e0b); box-shadow: 0 4px 12px rgba(251, 191, 36, 0.35); }
    .grade-d { background: linear-gradient(135deg, #f97316, #ea580c); box-shadow: 0 4px 12px rgba(249, 115, 22, 0.35); }
    .grade-e { background: linear-gradient(135deg, #ef4444, #dc2626); box-shadow: 0 4px 12px rgba(239, 68, 68, 0.35); }

    .grade-label {
      font-size: 0.88rem;
      color: #a8b2c1;
      font-weight: 500;
    }

    .ai-insight {
      background: rgba(79, 172, 254, 0.06);
      border-left: 3px solid #4facfe;
      border-radius: 0 10px 10px 0;
      padding: 12px 16px;
      font-size: 0.85rem;
      color: #8b9bb4;
      line-height: 1.6;
    }

    .ai-insight i {
      color: #4facfe;
    }

    .no-data {
      text-align: center;
      padding: 30px 10px;
      color: #5c6a7e;
      font-size: 0.95rem;
    }

    .no-data i {
      color: #4facfe;
      margin-right: 8px;
    }

    /* ===== 圖表 ===== */
    .chart-card {
      background: #131524;
      border-radius: 16px;
      border: 1px solid rgba(255, 255, 255, 0.06);
      padding: 28px 24px;
      box-shadow: 0 10px 40px rgba(0, 0, 0, 0.4);
    }

    .chart-title {
      color: #ffffff;
      font-weight: 700;
      font-size: 1.2rem;
      margin-bottom: 20px;
    }

    .chart-title i {
      color: #4facfe;
    }

    /* ===== 空狀態 ===== */
    .empty-state {
      text-align: center;
      padding: 80px 20px;
      color: #5c6a7e;
    }

    .empty-state i {
      font-size: 4rem;
      color: #1d3557;
      margin-bottom: 20px;
    }

    .empty-state h4 {
      color: #8b9bb4;
      font-weight: 600;
      margin-bottom: 10px;
    }

    /* ===== 響應式 ===== */
    @media (max-width: 600px) {
      .hero-title {
        font-size: 2rem;
      }

      .search-container {
        padding: 30px 20px;
      }

      .pe-value {
        font-size: 1.8rem;
      }
    }

    /* waiting overlay */
    .loading-content {
      text-align: center;
      color: #ffffff;
    }
  </style>
</head>

<body>
  {% include 'partials/navbar.html' %}

  <div class="hero-section">
    <div class="container">
      <h1 class="hero-title mb-2">
        <i class="fas fa-eye me-2"></i>自選股戰情室
      </h1>
      <p class="hero-subtitle">即時 PE 估值追蹤 · AI 洞察分析</p>

      <!-- 新增股票表單 -->
      <div class="search-container">
        <h3><i class="fas fa-plus-circle me-2" style="color:#4facfe;"></i>加入追蹤</h3>
        <p>輸入股票代碼，即時獲得 PE 估值分析與 AI 洞察</p>
        <form action="{{ url_for('watchlist.add_watchlist') }}" method="POST" onsubmit="triggerPageTransition()">
          <input type="text" name="stock_code" placeholder="輸入股票代碼，例如：2330" required
            pattern="[0-9]{4,6}" title="請輸入 4-6 位數字股票代碼">
          <button type="submit" class="btn-submit-custom">
            <i class="fas fa-bolt me-2"></i>加入追蹤
          </button>
        </form>
      </div>

      {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
      <div class="mt-3" style="max-width:520px;margin:0 auto;">
        {% for category, message in messages %}
        <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert"
          style="background:#131524;border:1px solid rgba(255,255,255,0.08);color:#e4e7eb;">
          {{ message }}
          <button type="button" class="btn-close" data-bs-dismiss="alert"
            style="filter:invert(1);"></button>
        </div>
        {% endfor %}
      </div>
      {% endif %}
      {% endwith %}
    </div>
  </div>

  <!-- 自選股卡片區域 -->
  <div class="container py-4">
    {% if items %}
    <div class="row g-4" id="watchlist-cards">
      {% for item in items %}
      <div class="col-12 col-sm-6 col-lg-4 col-xl-3">
        <div class="stock-card">
          <div class="stock-card-header">
            <div>
              <div class="stock-code">{{ item.stock_code }}</div>
              <div class="stock-name">{{ item.stock_name }}</div>
            </div>
            <form action="{{ url_for('watchlist.remove_watchlist', item_id=item.id) }}" method="POST"
              onsubmit="return confirm('確定要移除 {{ item.stock_code }} 嗎？')">
              <button type="submit" class="btn-remove" title="移除">
                <i class="fas fa-times"></i>
              </button>
            </form>
          </div>

          <div class="stock-card-body">
            {% if item.pe_ratio is not none %}
            <div class="pe-display">
              <span class="pe-label">PE 比率</span>
              <span class="pe-value {{ 'pe-low' if item.pe_ratio < 20 else ('pe-mid' if item.pe_ratio < 25 else 'pe-high') }}">
                {{ "%.2f"|format(item.pe_ratio) }}
              </span>
            </div>

            <div class="grade-display">
              <span class="grade-badge grade-{{ item.pe_grade|lower }}">
                {{ item.pe_grade }}
              </span>
              <span class="grade-label">
                {% if item.pe_grade|upper == 'A' %}極度低估
                {% elif item.pe_grade|upper == 'B' %}低估
                {% elif item.pe_grade|upper == 'C' %}合理
                {% elif item.pe_grade|upper == 'D' %}高估
                {% elif item.pe_grade|upper == 'E' %}極度高估
                {% else %}無數據{% endif %}
              </span>
            </div>

            {% if item.ai_insight %}
            <div class="ai-insight">
              <i class="fas fa-robot me-1"></i>
              {{ item.ai_insight[:100] }}{% if item.ai_insight|length > 100 %}...{% endif %}
            </div>
            {% endif %}
            {% else %}
            <div class="no-data">
              <i class="fas fa-spinner fa-spin"></i>
              正在取得 PE 數據...
            </div>
            {% endif %}
          </div>
        </div>
      </div>
      {% endfor %}
    </div>

    <!-- ECharts 圖表 -->
    <div class="chart-section mt-5">
      <div class="chart-card">
        <h5 class="chart-title"><i class="fas fa-chart-bar me-2"></i>PE 比率比較</h5>
        <div id="pe-chart" style="width: 100%; height: 400px;"></div>
      </div>
    </div>

    {% else %}
    <div class="empty-state">
      <i class="fas fa-inbox"></i>
      <h4>自選股是空的</h4>
      <p>輸入股票代碼開始追蹤您的關注清單</p>
    </div>
    {% endif %}
  </div>

  {% include 'partials/footer.html' %}

  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
  <script src="{{ url_for('static', filename='js/transitions.js') }}"></script>
  <script>
    document.addEventListener('DOMContentLoaded', function () {
      var chartDiv = document.getElementById('pe-chart');
      if (!chartDiv) return;

      var chart = echarts.init(chartDiv);

      var stockCodes = [];
      var peValues = [];
      {% for item in items %}
      {% if item.pe_ratio is not none %}
      stockCodes.push('{{ item.stock_code }}');
      peValues.push({{ item.pe_ratio }});
      {% endif %}
      {% endfor %}

      var option = {
        backgroundColor: 'transparent',
        tooltip: {
          trigger: 'axis',
          backgroundColor: 'rgba(10, 11, 20, 0.9)',
          borderColor: '#1d3557',
          textStyle: { color: '#e4e7eb' }
        },
        grid: {
          left: '3%',
          right: '4%',
          bottom: '3%',
          containLabel: true
        },
        xAxis: {
          type: 'category',
          data: stockCodes,
          axisLabel: { color: '#a8b2c1', rotate: 45 },
          axisLine: { lineStyle: { color: '#1d3557' } }
        },
        yAxis: {
          type: 'value',
          axisLabel: { color: '#a8b2c1' },
          splitLine: { lineStyle: { color: 'rgba(29, 53, 87, 0.3)' } }
        },
        series: [{
          name: 'PE',
          type: 'bar',
          data: peValues,
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: '#4facfe' },
              { offset: 1, color: '#1d3557' }
            ])
          },
          emphasis: {
            itemStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: '#ff6b6b' },
                { offset: 1, color: '#5c0a0a' }
              ])
            }
          }
        }]
      };

      chart.setOption(option);
      window.addEventListener('resize', function () { chart.resize(); });
    });
  </script>
</body>

</html>
'''

pathlib.Path('c:/Users/David/Desktop/股票專案2/templates/watchlist.html').write_text(new_content, encoding='utf-8')
print('watchlist.html written successfully')
print(f'File size: {len(new_content)} chars')
