import asyncio
from collections import deque
from typing import Dict, List, Tuple
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .config import SCAN_SYMBOLS, SCAN_BARS, SCAN_BATCH, SCAN_INTERVAL_SEC
from .okx import OkxClient
from .storage import save_candles_csv


class Scanner:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.running = False
        self.symbols = deque(SCAN_SYMBOLS)
        self.bars: Dict[str, int] = dict(SCAN_BARS)
        self.batch = SCAN_BATCH
        self.interval_sec = SCAN_INTERVAL_SEC
        self.processed_batches = 0
        self.saved_files: List[str] = []

    def _next_batch_symbols(self) -> List[str]:
        out = []
        for _ in range(min(self.batch, len(self.symbols))):
            sym = self.symbols.popleft()
            out.append(sym)
            self.symbols.append(sym)
        return out

    async def _do_scan_once(self):
        client = OkxClient()
        try:
            syms = self._next_batch_symbols()
            tasks = []
            for inst in syms:
                for bar, limit in self.bars.items():
                    tasks.append(client.candles(inst, bar, limit))
            results = await asyncio.gather(*tasks, return_exceptions=True)
            i = 0
            for inst in syms:
                for bar, _ in self.bars.items():
                    res = results[i]
                    i += 1
                    if isinstance(res, Exception):
                        # 忽略错误，下一轮继续
                        continue
                    path = save_candles_csv(inst, bar, res)
                    if path not in self.saved_files:
                        self.saved_files.append(path)
            self.processed_batches += 1
        finally:
            await client.close()

    def start(self):
        if self.running:
            return
        self.scheduler.add_job(self._do_scan_once, "interval", seconds=self.interval_sec)
        self.scheduler.start()
        self.running = True

    def stop(self):
        if not self.running:
            return
        self.scheduler.remove_all_jobs()
        self.scheduler.shutdown(wait=False)
        self.running = False

    def reconfig(self, symbols: List[str], bars: Dict[str, int], batch: int, interval_sec: int):
        # 应用新配置并重置状态
        from collections import deque
        self.symbols = deque(symbols)
        self.bars = dict(bars)
        self.batch = batch
        self.interval_sec = interval_sec
        # 重启定时任务
        if self.running:
            self.stop()
            self.start()

    def status(self):
        return {
            "running": self.running,
            "symbols": list(self.symbols),
            "bars": self.bars,
            "batch": self.batch,
            "interval_sec": self.interval_sec,
            "next_batch": self._next_batch_symbols(),
            "processed_batches": self.processed_batches,
            "saved_files": self.saved_files[-20:],
        }


scanner = Scanner()
