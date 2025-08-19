# app/main.py
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, FileResponse
from typing import Optional
import os

from .config import API_KEY, DATA_DIR, DEFAULT_BARS
from .okx import OkxClient
from .scan import scanner
from .dashboard import dashboard_page

# —— 策略：熊猫系统（保留，便于回退/对比）——
from .strategy_panda import (
    evaluate_panda,
    scan_top as scan_top_panda,
    fetch_candles as fetch_candles_panda,
)

# —— 策略：新“日内交易系统”（EMA21/55/144 · 定势→找位→信号）——
from .strategy_custom import (
    evaluate_custom,
    scan_top as scan_top_custom,
    fetch_candles as fetch_candles_custom,
)

app = FastAPI(title="okx-fastapi", version="1.5.0")

# =========================
# 统一异常：全部转为 JSON
# =========================
@app.exception_handler(Exception)
async def _any_exc(_req: Request, exc: Exception):
    # 避免 ChatGPT Actions 出现 ContentTypeError：一律返回 application/json
    return JSONResponse(
        {"code": "-2", "error": "server_exception", "detail": str(exc)},
        status_code=200,
    )

# =========================
# 鉴权辅助：多种来源统一取 key
# =========================
def _extract_api_key(req: Request) -> Optional[str]:
    k = req.headers.get("x-api-key") or req.headers.get("X-Api-Key")
    if not k:
        auth = req.headers.get("authorization") or req.headers.get("Authorization")
        if auth and auth.lower().startswith("bearer "):
            k = auth.split(None, 1)[1].strip()
    if not k:
        qp = req.query_params
        k = qp.get("api_key") or qp.get("x-api-key")
    return k

# =========================
# 简单鉴权中间件
# =========================
@app.middleware("http")
async def check_api_key(request: Request, call_next):
    # 放行：健康检查 / 仪表盘 / 调试回显 / 文档
    open_paths = {"/health", "/dashboard", "/debug/echo", "/openapi.json", "/docs", "/redoc"}
    if request.url.path in open_paths:
        return await call_next(request)
    key = _extract_api_key(request)
    if key != API_KEY:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    return await call_next(request)

# =========================
# 调试：查看是否带上了密钥（仅回显是否存在与尾四位）
# =========================
@app.get("/debug/echo")
async def debug_echo(request: Request):
    k = _extract_api_key(request)
    masked = None if not k else ("***" + k[-4:])
    return {
        "has_key": bool(k),
        "key_tail": masked,
        "headers_seen": {
            "authorization_present": bool(request.headers.get("authorization")),
            "x-api-key_present": bool(request.headers.get("x-api-key")),
        },
    }

# =========================
# 基础
# =========================
@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/dashboard")
async def dashboard():
    return dashboard_page()

# =========================
# 行情代理（OKX）
# =========================
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
    # 默认根数：1D/4H/1H = 50；15m/5m = 150
    if limit is None:
        limit = DEFAULT_BARS.get(bar, 100)
    client = OkxClient()
    try:
        return await client.candles(inst_id, bar, int(limit))
    finally:
        await client.close()

# =========================
# 扫描控制（云端自跑）
# =========================
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

# =========================
# 文件访问（扫描结果）
# =========================
@app.get("/files/list")
async def files_list():
    os.makedirs(DATA_DIR, exist_ok=True)
    return {"files": [os.path.join(DATA_DIR, name) for name in os.listdir(DATA_DIR)]}

@app.get("/files/download")
async def files_download(path: str):
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, filename=os.path.basename(path))

# =========================
# 策略 · 熊猫系统（保留）
# =========================
@app.get("/strategy/panda/evaluate")
async def strategy_panda_evaluate(
    inst_id: str = Query(...),
    bar: str = Query("15m"),
    trend_bar: str = Query("1H"),
    limit: int = Query(150),
    risk_percent: float = Query(2.0),
    funds_total: float = Query(694.0),
    funds_split: int = Query(7),
    leverage: float = Query(5.0),
    exclude_btc_in_screen: bool = Query(True),
):
    raw_b = await fetch_candles_panda(inst_id, bar, limit)
    raw_t = await fetch_candles_panda(inst_id, trend_bar, limit)
    return evaluate_panda(
        inst_id, bar, raw_b, raw_t,
        risk_percent, funds_total, funds_split, leverage, exclude_btc_in_screen
    )

@app.get("/strategy/panda/scan")
async def strategy_panda_scan(
    inst_type: str = Query("SPOT"),
    top: int = Query(5),
    bar: str = Query("15m"),
    trend_bar: str = Query("1H"),
    limit: int = Query(150),
    risk_percent: float = Query(2.0),
    funds_total: float = Query(694.0),
    funds_split: int = Query(7),
    leverage: float = Query(5.0),
    exclude_btc_in_screen: bool = Query(True),
):
    return await scan_top_panda(
        inst_type, top, bar, trend_bar, limit,
        exclude_btc_in_screen, funds_total, funds_split, leverage, risk_percent
    )

# =========================
# 策略 · 新“日内交易系统”（EMA21/55/144）
# =========================
@app.get("/strategy/custom/evaluate")
async def strategy_custom_evaluate(
    inst_id: str = Query(...),
    bar: str = Query("15m"),
    trend_bar: str = Query("1H"),
    limit: int = Query(150),
    risk_percent: float = Query(2.0),
    funds_total: float = Query(694.0),
    funds_split: int = Query(7),
    leverage: float = Query(5.0),
    exclude_btc_in_screen: bool = Query(True),
):
    raw_b = await fetch_candles_custom(inst_id, bar, limit)
    raw_t = await fetch_candles_custom(inst_id, trend_bar, limit)
    return evaluate_custom(
        inst_id, bar, raw_b, raw_t,
        risk_percent, funds_total, funds_split, leverage, exclude_btc_in_screen
    )

@app.get("/strategy/custom/scan")
async def strategy_custom_scan(
    inst_type: str = Query("SPOT"),
    top: int = Query(5),
    bar: str = Query("15m"),
    trend_bar: str = Query("1H"),
    limit: int = Query(150),
    risk_percent: float = Query(2.0),
    funds_total: float = Query(694.0),
    funds_split: int = Query(7),
    leverage: float = Query(5.0),
    exclude_btc_in_screen: bool = Query(True),
):
    return await scan_top_custom(
        inst_type, top, bar, trend_bar, limit,
        exclude_btc_in_screen, funds_total, funds_split, leverage, risk_percent
    )
