from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse, FileResponse
from typing import Optional, List
import os

from .config import API_KEY, DATA_DIR, PORT, DEFAULT_BARS
from .okx import OkxClient
from .schemas import CandleQuery, ScanConfig, ScanStatus
from .scan import scanner
from .dashboard import dashboard_page

app = FastAPI(title="okx-fastapi", version="1.0.0")


# 简单 Header 鉴权
@app.middleware("http")
async def check_api_key(request, call_next):
    # 放行健康检查与 dashboard 静态页
    open_paths = ["/health", "/dashboard"]
    if request.url.path in open_paths:
        return await call_next(request)
    key = request.headers.get("x-api-key")
    if key != API_KEY:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    return await call_next(request)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/dashboard")
async def dashboard():
    return dashboard_page()


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
    # 默认根数逻辑：1D/4H/1H -> 50；15m/5m -> 150
    if limit is None:
        limit = DEFAULT_BARS.get(bar, 100)
    client = OkxClient()
    try:
        return await client.candles(inst_id, bar, int(limit))
    finally:
        await client.close()


@app.post("/scan/start")
async def scan_start(cfg: ScanConfig):
    scanner.reconfig(cfg.symbols, cfg.bars, cfg.batch, cfg.interval_sec)
    scanner.start()
    return {"started": True, **scanner.status()}


@app.post("/scan/stop")
async def scan_stop():
    scanner.stop()
    return {"stopped": True, **scanner.status()}


@app.get("/scan/status", response_model=ScanStatus)
async def scan_status():
    return scanner.status()


@app.get("/files/list")
async def files_list():
    files = []
    for name in os.listdir(DATA_DIR):
        files.append(os.path.join(DATA_DIR, name))
    return {"files": files}


@app.get("/files/download")
async def files_download(path: str):
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, filename=os.path.basename(path))
