from pydantic import BaseModel, Field
from typing import List, Dict, Optional


class CandleQuery(BaseModel):
    inst_id: str = Field(..., description="交易对，如 ETH-USDT")
    bar: str = Field(..., description="周期，如 1D/4H/1H/15m/5m")
    limit: int = Field(..., description="K 线根数")


class ScanConfig(BaseModel):
    symbols: List[str]
    bars: Dict[str, int]  # {"1D":50, "4H":50, "1H":50, "15m":150, "5m":150}
    batch: int = 5
    interval_sec: int = 30


class ScanStatus(BaseModel):
    running: bool
    symbols: List[str]
    bars: Dict[str, int]
    batch: int
    interval_sec: int
    next_batch: List[str]
    processed_batches: int
    saved_files: List[str]
