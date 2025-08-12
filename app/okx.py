import httpx
from typing import Any, Dict, List, Optional
from .config import OKX_BASE

TIMEOUT = httpx.Timeout(10.0, connect=10.0)
HEADERS = {
    "Accept": "application/json",
    "User-Agent": "okx-fastapi/1.1"  # 减少被风控几率
}

class OkxClient:
    def __init__(self):
        self._client = httpx.AsyncClient(timeout=TIMEOUT, headers=HEADERS)

    async def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{OKX_BASE}/api/v5{path}"
        try:
            r = await self._client.get(url, params=params)
            if r.status_code != 200:
                # 不抛异常，直接返回可读信息，避免 FastAPI 500
                return {
                    "code": str(r.status_code),
                    "error": "upstream_http_error",
                    "url": str(r.url),
                    "detail": r.text[:500]
                }
            return r.json()
        except httpx.RequestError as e:
            return {
                "code": "-1",
                "error": "network_error",
                "detail": str(e)
            }

    async def ticker(self, inst_id: str) -> Dict[str, Any]:
        return await self._get("/market/ticker", {"instId": inst_id})

    async def tickers(self, inst_type: str) -> Dict[str, Any]:
        return await self._get("/market/tickers", {"instType": inst_type})

    async def candles(self, inst_id: str, bar: str, limit: int) -> Dict[str, Any]:
        return await self._get("/market/candles", {"instId": inst_id, "bar": bar, "limit": limit})

    async def close(self):
        await self._client.aclose()
