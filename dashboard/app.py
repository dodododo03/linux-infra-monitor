import logging
import os

import pymysql
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

log = logging.getLogger("dashboard")
app = FastAPI(title="Linux Infra Monitor")

# DB 설정: 환경변수에서 읽는다 (비밀값을 코드에 두지 않는다)
DB_HOST = os.environ["DB_HOST"]
DB_PORT = int(os.getenv("DB_PORT", "3307"))
DB_USER = os.environ["DB_USER"]
DB_PASSWORD = os.environ["DB_PASSWORD"]
DB_NAME = os.getenv("DB_NAME", "infra_monitor")


def get_db_connection():
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset="utf8mb4",
        connect_timeout=5,
        cursorclass=pymysql.cursors.DictCursor,
    )


@app.get("/", response_class=HTMLResponse)
def dashboard():
    html_content = """
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Infra Monitor</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css">
        <style>
            :root {
                --bg: #09090b;
                --surface: rgba(255, 255, 255, 0.02);
                --surface-hover: rgba(255, 255, 255, 0.035);
                --border: rgba(255, 255, 255, 0.08);
                --border-strong: rgba(255, 255, 255, 0.14);
                --text: #fafafa;
                --text-2: #a1a1aa;
                --text-3: #52525b;
                --cpu: #a78bfa;
                --mem: #38bdf8;
                --disk: #71717a;
                --ok: #4ade80;
                --warn: #f87171;
                --font: 'Inter', 'Pretendard Variable', Pretendard, -apple-system, system-ui, sans-serif;
                --mono: 'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, monospace;
            }

            * { box-sizing: border-box; margin: 0; padding: 0; }

            html { background: var(--bg); }
            body {
                min-height: 100vh;
                font-family: var(--font);
                font-size: 14px;
                letter-spacing: -0.011em;
                color: var(--text);
                background:
                    radial-gradient(ellipse 80% 50% at 50% -20%, rgba(120, 119, 198, 0.10), transparent 70%),
                    var(--bg);
                -webkit-font-smoothing: antialiased;
                padding: 0 16px;
            }
            /* 미세한 노이즈 텍스처 (SVG 터뷸런스) */
            body::before {
                content: "";
                position: fixed;
                inset: 0;
                pointer-events: none;
                opacity: 0.035;
                background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
                z-index: 0;
            }

            .container { position: relative; z-index: 1; max-width: 1080px; margin: 0 auto; padding: 28px 0 48px; }

            /* ── 헤더 ── */
            header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding-bottom: 20px;
                margin-bottom: 28px;
                border-bottom: 1px solid var(--border);
            }
            .brand { display: flex; align-items: center; gap: 10px; }
            .logo {
                width: 22px; height: 22px; border-radius: 6px;
                background: linear-gradient(135deg, #fafafa 0%, #71717a 100%);
                box-shadow: 0 0 16px rgba(167, 139, 250, 0.25);
            }
            h1 { font-size: 15px; font-weight: 600; letter-spacing: -0.02em; }
            .crumb { color: var(--text-3); font-weight: 400; margin: 0 2px; }
            .sub { color: var(--text-2); font-weight: 500; }

            .meta { display: flex; align-items: center; gap: 12px; }
            .updated { font-family: var(--mono); font-size: 12px; color: var(--text-3); font-variant-numeric: tabular-nums; }
            .status {
                display: inline-flex; align-items: center; gap: 7px;
                height: 26px; padding: 0 10px;
                border: 1px solid var(--border);
                border-radius: 6px;
                font-size: 12px; font-weight: 500; letter-spacing: -0.005em;
                color: var(--text-2);
                background: var(--surface);
            }
            .dot { width: 6px; height: 6px; border-radius: 50%; background: var(--ok); box-shadow: 0 0 8px var(--ok); }
            .status.alert { color: var(--warn); border-color: rgba(248, 113, 113, 0.25); background: rgba(248, 113, 113, 0.06); }
            .status.alert .dot { background: var(--warn); box-shadow: 0 0 8px var(--warn); animation: blink 1.2s ease-in-out infinite; }
            .status.stale .dot { background: var(--text-3); box-shadow: none; }
            @keyframes blink { 50% { opacity: 0.3; } }

            /* ── 섹션 라벨 ── */
            .section-label {
                font-size: 12px; font-weight: 500; color: var(--text-2);
                letter-spacing: -0.005em; margin-bottom: 12px;
                display: flex; justify-content: space-between; align-items: center;
            }

            /* ── 카드 ── */
            .card {
                position: relative;
                background: linear-gradient(180deg, rgba(255,255,255,0.03) 0%, rgba(255,255,255,0.01) 100%);
                border: 1px solid var(--border);
                border-radius: 10px;
                box-shadow:
                    inset 0 1px 0 rgba(255, 255, 255, 0.04),
                    0 0 0 1px rgba(0, 0, 0, 0.3),
                    0 8px 24px -12px rgba(0, 0, 0, 0.6);
                transition: border-color 0.2s, box-shadow 0.2s;
            }
            .card:hover {
                border-color: var(--border-strong);
                box-shadow:
                    inset 0 1px 0 rgba(255, 255, 255, 0.06),
                    0 0 0 1px rgba(0, 0, 0, 0.3),
                    0 0 32px -8px var(--glow, rgba(255, 255, 255, 0.06));
            }

            .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 28px; }

            .metric { padding: 18px 18px 16px; --glow: rgba(255, 255, 255, 0.06); }
            .metric[data-key="cpu"]  { --accent: var(--cpu);  --glow: rgba(167, 139, 250, 0.18); }
            .metric[data-key="mem"]  { --accent: var(--mem);  --glow: rgba(56, 189, 248, 0.18); }
            .metric[data-key="disk"] { --accent: var(--disk); --glow: rgba(161, 161, 170, 0.14); }
            .metric.over { border-color: rgba(248, 113, 113, 0.35); --glow: rgba(248, 113, 113, 0.25); box-shadow: inset 0 1px 0 rgba(255,255,255,0.04), 0 0 28px -10px rgba(248, 113, 113, 0.45); }

            .metric-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
            .metric-name { display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 500; color: var(--text-2); }
            .swatch { width: 8px; height: 8px; border-radius: 2px; background: var(--accent); }
            .metric-tag {
                font-family: var(--font); font-size: 11px; font-weight: 500; color: var(--text-3);
                padding: 2px 6px; border: 1px solid var(--border); border-radius: 4px;
            }
            .metric.over .metric-tag { color: var(--warn); border-color: rgba(248, 113, 113, 0.3); }

            .value {
                font-family: var(--mono);
                font-size: 32px; font-weight: 500;
                letter-spacing: -0.04em;
                font-variant-numeric: tabular-nums;
                line-height: 1;
            }
            .value .unit { font-size: 16px; color: var(--text-3); margin-left: 2px; letter-spacing: 0; }
            .metric.over .value { color: var(--warn); }

            .bar { position: relative; height: 3px; margin-top: 16px; background: rgba(255,255,255,0.06); border-radius: 2px; overflow: visible; }
            .bar-fill { height: 100%; width: 0; background: var(--accent); border-radius: 2px; transition: width 0.6s cubic-bezier(.2,.8,.2,1); }
            .metric.over .bar-fill { background: var(--warn); }
            .bar-mark { position: absolute; top: -3px; width: 1px; height: 9px; background: var(--text-3); }

            .metric-foot { display: flex; justify-content: space-between; margin-top: 10px; font-family: var(--mono); font-size: 11px; color: var(--text-3); font-variant-numeric: tabular-nums; }

            /* ── 차트 ── */
            .chart-card { padding: 18px 18px 12px; }
            .chart-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
            .chart-title { font-size: 13px; font-weight: 500; color: var(--text); letter-spacing: -0.01em; }
            .legend { display: flex; gap: 14px; }
            .legend-item { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--text-2); cursor: pointer; user-select: none; transition: opacity 0.15s; }
            .legend-item.off { opacity: 0.35; }
            .legend-item .swatch { width: 10px; height: 2px; border-radius: 1px; }
            .chart-wrap { position: relative; height: 340px; }
            .grid > *, .chart-card, .chart-wrap { min-width: 0; }  /* 좁은 화면에서 캔버스가 레이아웃을 밀어내지 않게 */

            footer { margin-top: 20px; font-size: 12px; color: var(--text-3); display: flex; justify-content: space-between; }
            footer .mono { font-family: var(--mono); }

            @media (max-width: 760px) {
                .container { padding-top: 18px; }
                .grid { grid-template-columns: 1fr; }
                .updated { display: none; }
                .chart-head { flex-direction: column; align-items: flex-start; gap: 10px; }
                .chart-wrap { height: 260px; }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <div class="brand">
                    <div class="logo"></div>
                    <h1>infra-monitor <span class="crumb">/</span> <span class="sub">overview</span></h1>
                </div>
                <div class="meta">
                    <span class="updated" id="updated">--:--:--</span>
                    <span class="status stale" id="status"><span class="dot"></span><span id="status-text">연결 중</span></span>
                </div>
            </header>

            <div class="section-label"><span>리소스 사용률</span></div>
            <div class="grid">
                <div class="card metric" data-key="cpu">
                    <div class="metric-head">
                        <div class="metric-name"><span class="swatch"></span>CPU</div>
                        <span class="metric-tag" data-tag>정상</span>
                    </div>
                    <div class="value"><span data-val>--.-</span><span class="unit">%</span></div>
                    <div class="bar"><div class="bar-fill" data-bar></div><div class="bar-mark" style="left:80%"></div></div>
                    <div class="metric-foot"><span>avg <span data-avg>--.-</span>%</span><span>max <span data-max>--.-</span>%</span></div>
                </div>
                <div class="card metric" data-key="mem">
                    <div class="metric-head">
                        <div class="metric-name"><span class="swatch"></span>Memory</div>
                        <span class="metric-tag" data-tag>정상</span>
                    </div>
                    <div class="value"><span data-val>--.-</span><span class="unit">%</span></div>
                    <div class="bar"><div class="bar-fill" data-bar></div><div class="bar-mark" style="left:80%"></div></div>
                    <div class="metric-foot"><span>avg <span data-avg>--.-</span>%</span><span>max <span data-max>--.-</span>%</span></div>
                </div>
                <div class="card metric" data-key="disk">
                    <div class="metric-head">
                        <div class="metric-name"><span class="swatch"></span>Disk</div>
                        <span class="metric-tag" data-tag>정상</span>
                    </div>
                    <div class="value"><span data-val>--.-</span><span class="unit">%</span></div>
                    <div class="bar"><div class="bar-fill" data-bar></div><div class="bar-mark" style="left:80%"></div></div>
                    <div class="metric-foot"><span>avg <span data-avg>--.-</span>%</span><span>max <span data-max>--.-</span>%</span></div>
                </div>
            </div>

            <div class="card chart-card">
                <div class="chart-head">
                    <span class="chart-title">사용률 추이</span>
                    <div class="legend" id="legend">
                        <span class="legend-item" data-idx="0"><span class="swatch" style="background:var(--cpu)"></span>CPU</span>
                        <span class="legend-item" data-idx="1"><span class="swatch" style="background:var(--mem)"></span>Memory</span>
                        <span class="legend-item" data-idx="2"><span class="swatch" style="background:var(--disk)"></span>Disk</span>
                    </div>
                </div>
                <div class="chart-wrap"><canvas id="metricChart"></canvas></div>
            </div>

            <footer>
                <span>임계치 <span class="mono">80%</span> · 5초마다 갱신</span>
                <span class="mono" id="count"></span>
            </footer>
        </div>

        <script>
            const THRESHOLD = 80;
            const css = getComputedStyle(document.documentElement);
            const color = (name) => css.getPropertyValue(name).trim();
            const MONO = "'JetBrains Mono', ui-monospace, monospace";

            // 80% 임계치 점선을 그리는 작은 플러그인
            const thresholdLine = {
                id: 'thresholdLine',
                afterDatasetsDraw(chart) {
                    const { ctx, chartArea: a, scales: { y } } = chart;
                    const py = y.getPixelForValue(THRESHOLD);
                    ctx.save();
                    ctx.strokeStyle = 'rgba(248, 113, 113, 0.45)';
                    ctx.lineWidth = 1;
                    ctx.setLineDash([3, 4]);
                    ctx.beginPath(); ctx.moveTo(a.left, py); ctx.lineTo(a.right, py); ctx.stroke();
                    ctx.setLineDash([]);
                    ctx.fillStyle = 'rgba(248, 113, 113, 0.7)';
                    ctx.font = '10px ' + MONO;
                    ctx.textAlign = 'right';
                    ctx.fillText('threshold ' + THRESHOLD + '%', a.right - 4, py - 6);
                    ctx.restore();
                }
            };

            function fade(hex, alpha) {
                const n = parseInt(hex.slice(1), 16);
                return 'rgba(' + (n >> 16 & 255) + ',' + (n >> 8 & 255) + ',' + (n & 255) + ',' + alpha + ')';
            }
            function gradient(ctx, area, hex) {
                const g = ctx.createLinearGradient(0, area.top, 0, area.bottom);
                g.addColorStop(0, fade(hex, 0.12));
                g.addColorStop(1, fade(hex, 0));
                return g;
            }
            function series(label, hex, filled) {
                return {
                    label, data: [],
                    borderColor: hex,
                    borderWidth: 1.5,
                    pointRadius: 0,
                    pointHoverRadius: 3,
                    pointHoverBackgroundColor: hex,
                    pointHoverBorderWidth: 0,
                    tension: 0.35,
                    fill: filled,
                    backgroundColor: (c) => c.chart.chartArea ? gradient(c.chart.ctx, c.chart.chartArea, hex) : 'transparent',
                };
            }

            const chart = new Chart(document.getElementById('metricChart'), {
                type: 'line',
                data: { labels: [], datasets: [
                    series('CPU', color('--cpu'), true),
                    series('Memory', color('--mem'), true),
                    series('Disk', color('--disk'), false),
                ]},
                plugins: [thresholdLine],
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: { duration: 400, easing: 'easeOutQuart' },
                    interaction: { mode: 'index', intersect: false },
                    layout: { padding: { top: 4 } },
                    scales: {
                        y: {
                            min: 0, max: 100,
                            border: { display: false },
                            grid: { color: 'rgba(255,255,255,0.05)', drawTicks: false },
                            ticks: { stepSize: 25, padding: 10, color: '#52525b', font: { family: MONO, size: 11 }, callback: (v) => v + '%' },
                        },
                        x: {
                            border: { color: 'rgba(255,255,255,0.08)' },
                            grid: { display: false },
                            ticks: { color: '#52525b', font: { family: MONO, size: 11 }, maxRotation: 0, autoSkipPadding: 24 },
                        },
                    },
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            backgroundColor: 'rgba(24, 24, 27, 0.92)',
                            borderColor: 'rgba(255,255,255,0.1)',
                            borderWidth: 1,
                            cornerRadius: 6,
                            padding: 10,
                            boxWidth: 8, boxHeight: 8, boxPadding: 4,
                            usePointStyle: true,
                            titleColor: '#a1a1aa',
                            bodyColor: '#fafafa',
                            titleFont: { family: MONO, size: 11, weight: '400' },
                            bodyFont: { family: MONO, size: 12 },
                            callbacks: { label: (c) => ' ' + c.dataset.label.padEnd(7) + c.parsed.y.toFixed(1).padStart(5) + '%' },
                        },
                    },
                },
            });

            // 범례 클릭으로 시리즈 켜고 끄기
            document.querySelectorAll('.legend-item').forEach((el) => {
                el.addEventListener('click', () => {
                    const i = Number(el.dataset.idx);
                    const visible = chart.isDatasetVisible(i);
                    chart.setDatasetVisibility(i, !visible);
                    el.classList.toggle('off', visible);
                    chart.update();
                });
            });

            const fmt = (v) => Number(v).toFixed(1);

            function renderMetric(key, values) {
                const card = document.querySelector('.metric[data-key="' + key + '"]');
                const latest = values[values.length - 1];
                const avg = values.reduce((s, v) => s + v, 0) / values.length;
                const over = latest >= THRESHOLD;
                card.querySelector('[data-val]').textContent = fmt(latest);
                card.querySelector('[data-avg]').textContent = fmt(avg);
                card.querySelector('[data-max]').textContent = fmt(Math.max(...values));
                card.querySelector('[data-bar]').style.width = Math.min(latest, 100) + '%';
                card.querySelector('[data-tag]').textContent = over ? '초과' : '정상';
                card.classList.toggle('over', over);
            }

            function setStatus(kind, text) {
                const el = document.getElementById('status');
                el.className = 'status' + (kind ? ' ' + kind : '');
                document.getElementById('status-text').textContent = text;
            }

            async function fetchData() {
                try {
                    const res = await fetch('/api/metrics?limit=60');
                    if (!res.ok) throw new Error('HTTP ' + res.status);
                    const data = await res.json();
                    if (data.length === 0) { setStatus('stale', '데이터 없음'); return; }

                    const cpu = data.map((d) => d.cpu_usage);
                    const mem = data.map((d) => d.mem_usage);
                    const disk = data.map((d) => d.disk_usage);

                    renderMetric('cpu', cpu);
                    renderMetric('mem', mem);
                    renderMetric('disk', disk);

                    const last = data[data.length - 1];
                    if (last.is_alert) setStatus('alert', 'Alert');
                    else setStatus('', 'Operational');
                    document.getElementById('updated').textContent = 'last ' + last.created_at;
                    document.getElementById('count').textContent = data.length + ' samples';

                    chart.data.labels = data.map((d) => d.created_at);
                    chart.data.datasets[0].data = cpu;
                    chart.data.datasets[1].data = mem;
                    chart.data.datasets[2].data = disk;
                    chart.update();
                } catch (err) {
                    console.error('데이터 갱신 실패:', err);
                    setStatus('stale', '연결 끊김');
                }
            }

            fetchData();
            setInterval(fetchData, 5000);
        </script>
    </body>
    </html>
    """
    return html_content


@app.get("/health")
def health():
    """컨테이너 헬스체크용: DB까지 연결되는지 확인"""
    try:
        conn = get_db_connection()
        conn.close()
        return {"status": "ok"}
    except pymysql.MySQLError:
        raise HTTPException(status_code=503, detail="database unavailable")


# async def가 아니라 def인 이유:
# pymysql은 동기(블로킹) 라이브러리라 async def 안에서 호출하면 이벤트 루프 전체가 멈춘다.
# def로 선언하면 FastAPI가 스레드풀에서 실행해 다른 요청을 막지 않는다.
@app.get("/api/metrics")
def get_metrics(limit: int = 20):
    limit = max(1, min(limit, 500))
    try:
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT cpu_usage, mem_usage, disk_usage, is_alert, created_at"
                    " FROM system_metrics ORDER BY id DESC LIMIT %s",
                    (limit,),
                )
                rows = cursor.fetchall()
        finally:
            conn.close()
    except pymysql.MySQLError:
        # 내부 에러 내용은 로그에만 남기고, 응답에는 노출하지 않는다
        log.exception("메트릭 조회 실패")
        raise HTTPException(status_code=500, detail="failed to load metrics")

    for row in rows:
        row["created_at"] = row["created_at"].strftime("%H:%M:%S")
    rows.reverse()
    return rows
