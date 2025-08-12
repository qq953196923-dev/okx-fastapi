from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, FileResponse
from typing import Optional
import os

from .config import API_KEY, DATA_DIR, DEFAULT_BARS
from .okx import OkxClient
from .scan import scanner
from .dashboard import dashboard_page

app = FastAPI(title="okx-fastapi", version="1.1.2")

# 统一把未捕获异常转成 JSON，避免 Actions 出现 ContentTypeError
@app.exception_handler(Exception)
async def _any_exc(_req: Request, exc: Exception):
    return JSONResponse(
        {"code": "-2", "error": "server_exception", "detail": str(exc)},
        status_code=200
    )

# 简单 Header 鉴权：放行 /health 与 /dashboard，其它都需要 x-api-key
@app.middleware("http")
async def check_api_key(request: Request, call_next):
    if request.url.path in ("/health", "/dashboard"):
        return await call_next(request)
    key = request.headers.get("x-api-key")
    if key != API_KEY:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    return await call_next(request)

# ---- 基础 ----
@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/dashboard")
async def dashboard():
    return dashboard_page()

# ---- 行情代理 ----
@app.get("/ticker")
async def get_ticker(inst_id: str = Query(..., alias="inst_id")):
    client = OkxClient()
    try:
        return await client.ticker(inst_id)
    finally:
        await client.close()

@app.get("/tickers")
async def get_tickers(inst_type: str = Query("SPOT", alias="inst_type")):
    client = OkxClient()
    try:
        return await client.tickers(inst_type)
    finally:
        await client.close()

@app.get("/candles")
async def get_candles(inst_id: str, bar: str, limit: Optional[int] = None):
    if limit is None:
        limit = DEFAULT_BARS.get(bar, 100)  # 1D/4H/1H=50，15m/5m=150
    client = OkxClient()
    try:
        return await client.candles(inst_id, bar, int(limit))
    finally:
        await client.close()

# ---- 扫描控制 ----
@app.post("/scan/start")
async def scan_start(cfg: dict):
    symbols = cfg.get("symbols") or []
    bars = cfg.get("bars") or DEFAULT_BARS
    batch = int(cfg.get("batch", 5))
    interval_sec = int(cfg.get("interval_sec", 30))
    scanner.reconfig(symbols, bars, batch, interval_sec)
    scanner.start()
    return {"started": True, **scanner.status()}

@app.post("/scan/stop")
async def scan_stop():
    scanner.stop()
    return {"stopped": True, **scanner.status()}

@app.get("/scan/status")
async def scan_status():
    return scanner.status()

# ---- 文件访问 ----
@app.get("/files/list")
async def files_list():
    os.makedirs(DATA_DIR, exist_ok=True)
    return {"files": [os.path.join(DATA_DIR, name) for name in os.listdir(DATA_DIR)]}

@app.get("/files/download")
async def files_download(path: str):
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, filename=os.path.basename(path))
