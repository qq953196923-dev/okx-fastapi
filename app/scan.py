import asyncio
from collections import deque
from typing import Dict, List

from .config import SCAN_SYMBOLS, SCAN_BARS, SCAN_BATCH, SCAN_INTERVAL_SEC
from .okx import OkxClient
from .storage import save_candles_csv


class Scanner:
    """
    简单可靠的后台扫描器：
    - 使用 asyncio.create_task 启动循环，不依赖 APScheduler
    - 每 interval_sec 跑一批（batch 个 symbol × 所有周期）
    - 结果追加到 CSV；状态里返回 processed_batches / saved_files
    """
    def __init__(self):
        self.running: bool = False
        self._task: asyncio.Task | None = None

        self.symbols = deque(SCAN_SYMBOLS)
        self.bars: Dict[str, int] = dict(SCAN_BARS)
        self.batch: int = SCAN_BATCH
        self.interval_sec: int = SCAN_INTERVAL_SEC

        self.processed_batches: int = 0
        self.saved_files: List[str] = []

    # ---- 批次计算 ----
    def _peek_next_batch(self) -> List[str]:
        n = min(self.batch, len(self.symbols))
        return [self.symbols[i] for i in range(n)]

    def _next_batch(self) -> List[str]:
        out: List[str] = []
        for _ in range(min(self.batch, len(self.symbols))):
            s = self.symbols.popleft()
            out.append(s)
            self.symbols.append(s)
        return out

    # ---- 主循环 ----
    async def _runner(self):
        try:
            while self.running:
                await self._do_scan_once()
                await asyncio.sleep(self.interval_sec)
        except asyncio.CancelledError:
            # 停止时取消即可
            pass

    async def _do_scan_once(self):
        syms = self._next_batch()
        if not syms:
            return

        client = OkxClient()
        try:
            tasks = []
            for inst in syms:
                for bar, limit in self.bars.items():
                    tasks.append(client.candles(inst, bar, limit))
            results = await asyncio.gather(*tasks, return_exceptions=True)

            i = 0
            for inst in syms:
                for bar in self.bars.keys():
                    res = results[i]
                    i += 1
                    if isinstance(res, Exception):
                        # 忽略该条错误，下一轮继续
                        continue
                    # 即便 data 为空，也会落一个带表头的 CSV，便于可视化与验证
                    path = save_candles_csv(inst, bar, res)
                    if path not in self.saved_files:
                        self.saved_files.append(path)

            self.processed_batches += 1
        finally:
            await client.close()

    # ---- 控制 ----
    def start(self):
        if self.running:
            return
        self.running = True
        # 启动后台循环
        self._task = asyncio.create_task(self._runner())

    def stop(self):
        if not self.running:
            return
        self.running = False
        if self._task:
            self._task.cancel()
            self._task = None

    def reconfig(self, symbols: List[str], bars: Dict[str, int], batch: int, interval_sec: int):
        self.symbols = deque(symbols or [])
        self.bars = dict(bars or {})
        self.batch = int(batch)
        self.interval_sec = int(interval_sec)
        # 运行中则重启
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
            "next_batch": self._peek_next_batch(),   # 仅查看，不改变队列
            "processed_batches": self.processed_batches,
            "saved_files": self.saved_files[-20:],    # 仅展示最近 20 个
        }


scanner = Scanner()
