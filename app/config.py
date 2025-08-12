import os
from typing import Dict, List, Tuple

DEFAULT_BARS = {
    "1D": 50,
    "4H": 50,
    "1H": 50,
    "15m": 150,
    "5m": 150,
}

def parse_symbols(s: str) -> List[str]:
    return [x.strip() for x in s.split(",") if x.strip()]

def parse_bars(s: str) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for part in s.split(","):
        if not part.strip():
            continue
        bar, limit = part.split(":")
        out[bar.strip()] = int(limit)
    return out

API_KEY = os.getenv("API_KEY", "change-me")
# 改到 Render 可写临时盘
DATA_DIR = os.getenv("DATA_DIR", "/var/tmp/okxdata")
SCAN_SYMBOLS = parse_symbols(os.getenv("SCAN_SYMBOLS", "ETH-USDT,SOL-USDT,BNB-USDT,OP-USDT,ARB-USDT"))
SCAN_BARS = parse_bars(os.getenv("SCAN_BARS", ",".join([f"{k}:{v}" for k, v in DEFAULT_BARS.items()])))
SCAN_BATCH = int(os.getenv("SCAN_BATCH", "5"))
SCAN_INTERVAL_SEC = int(os.getenv("SCAN_INTERVAL_SEC", "30"))
OKX_BASE = os.getenv("OKX_BASE", "https://www.okx.com")
PORT = int(os.getenv("PORT", "8000"))
