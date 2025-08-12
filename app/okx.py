import httpx
from typing import Any, Dict, List, Optional

from .config import OKX_BASE

TIMEOUT = httpx.Timeout(10.0, connect=10.0)
HEADERS = {"Accept": "application/json"}


class OkxClient:
    def __init__(self):
        self._client = httpx.AsyncClient(timeout=TIMEOUT, headers=HEADERS)

    async def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{OKX_BASE}/api/v5{path}"
        r = await self._client.get(url, params=params)
        r.raise_for_status()
        return r.json()

    async def ticker(self, inst_id: str) -> Dict[str, Any]:
        return await self._get("/market/ticker", {"instId": inst_id})

    async def tickers(self, inst_type: str) -> Dict[str, Any]:
        # inst_type: SPOT, SWAP, FUTURES, OPTION
        return await self._get("/market/tickers", {"instType": inst_type})

    async def candles(self, inst_id: str, bar: str, limit: int) -> Dict[str, Any]:
        # bar: 1m,5m,15m,1H,4H,1D,1W,1M...
        return await self._get("/market/candles", {"instId": inst_id, "bar": bar, "limit": limit})

    async def close(self):
        await self._client.aclose()
