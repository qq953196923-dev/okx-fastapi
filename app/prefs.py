import os, json
from typing import Dict, Any
from .config import DATA_DIR, DEFAULT_BARS

PREFS_PATH = os.path.join(DATA_DIR, "prefs.json")

DEFAULT_PREFS: Dict[str, Any] = {
    "exclude_symbols": ["BTC-USDT", "BTC"],  # 默认排除
    "risk_max_percent": 2,                    # 最大风控风险（%）
    "bars": DEFAULT_BARS,                     # K线根数默认
    "batch": 5,
    "interval_sec": 30
}

def read_prefs() -> Dict[str, Any]:
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.isfile(PREFS_PATH):
        with open(PREFS_PATH, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_PREFS, f, ensure_ascii=False, indent=2)
        return dict(DEFAULT_PREFS)
    with open(PREFS_PATH, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return dict(DEFAULT_PREFS)

def update_prefs(patch: Dict[str, Any]) -> Dict[str, Any]:
    cur = read_prefs()
    cur.update(patch or {})
    with open(PREFS_PATH, "w", encoding="utf-8") as f:
        json.dump(cur, f, ensure_ascii=False, indent=2)
    return cur
