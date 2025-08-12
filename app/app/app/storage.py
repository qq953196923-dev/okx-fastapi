import os
import csv
from typing import Dict, List
from .config import DATA_DIR

os.makedirs(DATA_DIR, exist_ok=True)


def _csv_path(inst_id: str, bar: str) -> str:
    safe_inst = inst_id.replace("/", "-")
    return os.path.join(DATA_DIR, f"{safe_inst}_{bar}.csv")


def save_candles_csv(inst_id: str, bar: str, raw: Dict) -> str:
    # OKX格式 data: [[ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm], ...]
    data = raw.get("data", [])
    path = _csv_path(inst_id, bar)
    # 若不存在则写表头
    need_header = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if need_header:
            writer.writerow(["ts", "open", "high", "low", "close", "vol", "volCcy", "volCcyQuote", "confirm"])
        for row in data:
            # 有些字段可能缺失，统一填充长度
            row = list(row) + [None] * (9 - len(row))
            writer.writerow(row[:9])
    return path
