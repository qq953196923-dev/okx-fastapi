from fastapi.responses import HTMLResponse

DASHBOARD_HTML = """
<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\"/>
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"/>
  <title>OKX-GPT Dashboard</title>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, PingFang SC, Noto Sans SC, sans-serif; margin: 24px; }
    .card { padding: 16px; border: 1px solid #e5e7eb; border-radius: 12px; box-shadow: 0 1px 2px rgba(0,0,0,.05); margin-bottom: 16px; }
    input, textarea { width: 100%; padding: 8px; border: 1px solid #e5e7eb; border-radius: 8px; margin-top: 8px; }
    button { padding: 8px 12px; border-radius: 8px; border: 1px solid #d1d5db; background: #f9fafb; cursor: pointer; }
    pre { background: #f8fafc; padding: 12px; border-radius: 8px; overflow-x: auto; }
  </style>
</head>
<body>
  <h1>OKX-GPT Dashboard</h1>

  <div class="card">
    <h3>状态</h3>
    <pre id="status">加载中...</pre>
    <button onclick="refresh()">刷新</button>
  </div>

  <div class="card">
    <h3>扫描配置</h3>
    <label>Symbols (逗号分隔)</label>
    <input id="symbols" placeholder="ETH-USDT,SOL-USDT" />
    <label>Bars (格式: 1D:50,4H:50,1H:50,15m:150,5m:150)</label>
    <input id="bars" placeholder="1D:50,4H:50,1H:50,15m:150,5m:150" />
    <label>Batch (每批数量)</label>
    <input id="batch" type="number" value="5" />
    <label>Interval Sec (批间隔秒数)</label>
    <input id="interval" type="number" value="30" />
    <div style="margin-top:8px;">
      <button onclick="start()">启动扫描</button>
      <button onclick="stop()">停止扫描</button>
    </div>
  </div>

  <script>
    async function refresh(){
      const r = await fetch('/scan/status');
      const j = await r.json();
      document.getElementById('status').textContent = JSON.stringify(j, null, 2);
    }
    async function start(){
      const body = {
        symbols: document.getElementById('symbols').value.split(',').map(s=>s.trim()).filter(Boolean),
        bars: Object.fromEntries(document.getElementById('bars').value.split(',').map(x=>x.trim()).filter(Boolean).map(p=>p.split(':'))),
        batch: parseInt(document.getElementById('batch').value),
        interval_sec: parseInt(document.getElementById('interval').value),
      };
      // 转换 bars 的值为 number
      for(const k in body.bars){ body.bars[k] = parseInt(body.bars[k]); }
      await fetch('/scan/start', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
      refresh();
    }
    async function stop(){
      await fetch('/scan/stop', {method:'POST'});
      refresh();
    }
    refresh();
  </script>
</body>
</html>
"""


def dashboard_page():
    return HTMLResponse(DASHBOARD_HTML)
