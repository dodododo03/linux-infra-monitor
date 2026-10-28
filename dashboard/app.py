from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
import pymysql

app = FastAPI()

# DB 설정 (우리 MariaDB 정보)
DB_HOST = "192.168.1.105"
DB_USER = "monitor_user"
DB_PASSWORD = "1234"
DB_NAME = "infra_monitor"
DB_PORT = 3307


def get_db_connection():
  return pymysql.connect(
      host=DB_HOST,
      user=DB_USER,
      password=DB_PASSWORD,
      database=DB_NAME,
      port=DB_PORT,
      charset="utf8mb4",
      cursorclass=pymysql.cursors.DictCursor,
  )


@app.get("/", response_class=HTMLResponse)
async def dashboard():
  html_content = """
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>실시간 서버 인프라 모니터링</title>
        <!-- Chart.js & Google Fonts -->
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;600&family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
        <style>
            :root {
                --bg-color: #0f172a;
                --card-bg: #1e293b;
                --text-primary: #f8fafc;
                --text-secondary: #94a3b8;
                --accent-blue: #38bdf8;
                --accent-pink: #f43f5e;
                --accent-green: #22c55e;
                --border-color: #334155;
            }

            * { box-sizing: border-box; margin: 0; padding: 0; }
            body {
                font-family: 'Inter', 'Fira Code', monospace;
                background-color: var(--bg-color);
                color: var(--text-primary);
                padding: 20px;
                display: flex;
                justify-content: center;
            }

            .container {
                width: 100%;
                max-width: 1000px;
            }

            header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 24px;
                border-bottom: 1px solid var(--border-color);
                padding-bottom: 16px;
            }

            h1 { font-size: 1.4rem; font-weight: 700; color: var(--accent-blue); display: flex; align-items: center; gap: 10px; }
            .status-badge {
                background-color: rgba(34, 197, 94, 0.15);
                color: var(--accent-green);
                padding: 6px 12px;
                border-radius: 20px;
                font-size: 0.85rem;
                font-weight: 600;
                display: flex;
                align-items: center;
                gap: 6px;
            }
            .status-dot { width: 8px; height: 8px; background-color: var(--accent-green); border-radius: 50%; animation: pulse 2s infinite; }

            @keyframes pulse {
                0% { transform: scale(0.95); opacity: 0.8; }
                50% { transform: scale(1.2); opacity: 1; }
                100% { transform: scale(0.95); opacity: 0.8; }
            }

            /* 카드 레이아웃 (반응형 그리드) */
            .grid-cards {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
                gap: 16px;
                margin-bottom: 24px;
            }

            .card {
                background-color: var(--card-bg);
                border: 1px solid var(--border-color);
                border-radius: 12px;
                padding: 20px;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            }

            .card-title { font-size: 0.9rem; color: var(--text-secondary); margin-bottom: 8px; font-weight: 600; }
            .card-value { font-size: 1.8rem; font-weight: 700; font-family: 'Fira Code', monospace; }

            /* 그래프 영역 */
            .chart-container {
                background-color: var(--card-bg);
                border: 1px solid var(--border-color);
                border-radius: 12px;
                padding: 20px;
                position: relative;
                height: 400px;
            }

            /* 반응형 조정 */
            @media (max-width: 768px) {
                body { padding: 10px; }
                h1 { font-size: 1.1rem; }
                .chart-container { height: 300px; }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>🖥️ 실시간 서버 인프라 모니터링</h1>
                <div class="status-badge">
                    <div class="status-dot"></div>
                    SYSTEM LIVE
                </div>
            </header>

            <div class="grid-cards">
                <div class="card">
                    <div class="card-title">현재 CPU 사용량</div>
                    <div class="card-value" id="cpu-val">0.0%</div>
                </div>
                <div class="card">
                    <div class="card-title">현재 메모리 사용량</div>
                    <div class="card-value" id="mem-val">0.0%</div>
                </div>
                <div class="card">
                    <div class="card-title">현재 디스크 사용량</div>
                    <div class="card-value" id="disk-val">0.0%</div>
                </div>
            </div>

            <div class="chart-container">
                <canvas id="metricChart"></canvas>
            </div>
        </div>

        <script>
            const ctx = document.getElementById('metricChart').getContext('2d');
            const metricChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [
                        { 
                            label: 'CPU Usage (%)', 
                            borderColor: '#f43f5e', 
                            backgroundColor: 'rgba(244, 63, 94, 0.1)', 
                            borderWidth: 2,
                            fill: true,
                            data: [], 
                            tension: 0.3 
                        },
                        { 
                            label: 'Memory Usage (%)', 
                            borderColor: '#38bdf8', 
                            backgroundColor: 'rgba(56, 189, 248, 0.1)', 
                            borderWidth: 2,
                            fill: true,
                            data: [], 
                            tension: 0.3 
                        }
                    ]
                },
                options: { 
                    responsive: true, 
                    maintainAspectRatio: false,
                    animation: {
                        duration: 750, // 부드러운 실시간 슬라이딩 애니메이션 효과
                        easing: 'linear'
                    },
                    scales: { 
                        y: { 
                            beginAtZero: true, 
                            max: 100,
                            grid: { color: '#334155' },
                            ticks: { color: '#94a3b8' }
                        },
                        x: {
                            grid: { display: false },
                            ticks: { color: '#94a3b8' }
                        }
                    },
                    plugins: {
                        legend: { labels: { color: '#f8fafc', font: { family: 'Fira Code' } } }
                    }
                }
            });

            async function fetchData() {
                try {
                    const response = await fetch('/api/metrics');
                    const data = await response.json();
                    
                    if (data.length === 0) return;

                    const labels = data.map(item => item.created_at);
                    const cpuData = data.map(item => item.cpu_usage);
                    const memData = data.map(item => item.mem_usage);
                    const diskData = data.map(item => item.disk_usage);

                    const latestCpu = cpuData[cpuData.length - 1];
                    const latestMem = memData[memData.length - 1];
                    const latestDisk = diskData[diskData.length - 1];

                    document.getElementById('cpu-val').innerText = latestCpu + '%';
                    document.getElementById('mem-val').innerText = latestMem + '%';
                    document.getElementById('disk-val').innerText = latestDisk + '%';

                    metricChart.data.labels = labels;
                    metricChart.data.datasets[0].data = cpuData;
                    metricChart.data.datasets[1].data = memData;
                    metricChart.update();
                } catch (error) {
                    console.error('데이터 갱신 실패:', error);
                }
            }

            setInterval(fetchData, 5000);
            fetchData();
        </script>
    </body>
    </html>
    """
  return html_content


@app.get("/api/metrics")
async def get_metrics():
  try:
    conn = get_db_connection()
    with conn.cursor() as cursor:
      sql = """
                SELECT cpu_usage, mem_usage, disk_usage, created_at 
                FROM system_metrics 
                ORDER BY id DESC LIMIT 20
            """
      cursor.execute(sql)
      result = cursor.fetchall()
      for row in result:
        row["created_at"] = row["created_at"].strftime("%H:%M:%S")
      result.reverse()
    conn.close()
    return result
  except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))
