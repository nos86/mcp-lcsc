from __future__ import annotations

import asyncio
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx

from .config import KNOWN_PDF_HOSTS, Settings


class LcscApiError(RuntimeError):
    pass


class LcscPermanentError(LcscApiError):
    pass


class LcscClient:
    # NOTE: endpoints below are documented assumptions; may require updates if LCSC changes.
    search_endpoint = "https://wmsc.lcsc.com/ftps/wm/search/global"
    detail_endpoint = "https://wmsc.lcsc.com/ftps/wm/product/detail"

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self._client = client
        self._last_request_at = 0.0

    async def __aenter__(self) -> "LcscClient":
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=20,
                headers={"User-Agent": self.settings.user_agent, "Accept": "application/json, text/plain, */*"},
            )
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._client is not None:
            await self._client.aclose()

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("HTTP client not initialized")
        return self._client

    async def _throttle(self) -> None:
        min_interval = 1.0 / max(self.settings.requests_per_second, 0.1)
        now = time.monotonic()
        wait_for = min_interval - (now - self._last_request_at)
        if wait_for > 0:
            await asyncio.sleep(wait_for)
        self._last_request_at = time.monotonic()

    async def _request(self, method: str, url: str, **kwargs: object) -> httpx.Response:
        backoff = 0.5
        last_error: Exception | None = None
        for _ in range(3):
            try:
                await self._throttle()
                response = await self.client.request(method, url, **kwargs)
                if response.status_code == 404:
                    raise LcscPermanentError("Component not found")
                if response.status_code == 403:
                    raise LcscPermanentError("Access blocked by upstream (possible anti-bot protection)")
                if response.status_code in {429, 500, 502, 503, 504}:
                    raise LcscApiError(f"Upstream temporary failure ({response.status_code})")
                if 400 <= response.status_code < 500:
                    raise LcscPermanentError(f"Upstream client error ({response.status_code})")
                response.raise_for_status()
                return response
            except LcscPermanentError:
                raise
            except (httpx.RequestError, LcscApiError) as exc:
                last_error = exc
                await asyncio.sleep(backoff)
                backoff *= 2
        raise LcscApiError(f"LCSC request failed: {last_error}") from last_error

    async def search(self, query: str, limit: int, in_stock_only: bool, basic_only: bool) -> tuple[dict, str]:
        params = {
            "keyword": query,
            "pageNum": 1,
            "pageSize": limit,
            "inStockOnly": int(in_stock_only),
            "basicOnly": int(basic_only),
        }
        response = await self._request("GET", self.search_endpoint, params=params)
        return response.json(), str(response.url)

    async def component(self, lcsc_id: str) -> tuple[dict, str]:
        params = {"productCode": lcsc_id}
        response = await self._request("GET", self.detail_endpoint, params=params)
        return response.json(), str(response.url)

    async def download_pdf(self, lcsc_id: str, datasheet_url: str, destination: Path) -> tuple[str, int]:
        parsed = urlparse(datasheet_url)
        if parsed.scheme.lower() != "https":
            raise LcscApiError("Datasheet URL must use https")
        if (parsed.hostname or "").lower() not in KNOWN_PDF_HOSTS:
            raise LcscApiError("Datasheet URL host is not in allow-list")

        response = await self._request("GET", datasheet_url)
        content = response.content
        if len(content) > self.settings.max_pdf_size_bytes:
            raise LcscApiError("PDF exceeds configured max size")
        if not content.startswith(b"%PDF"):
            raise LcscApiError("Downloaded file is not a valid PDF header")

        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        return hashlib.sha256(content).hexdigest(), len(content)



def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def first_dict(data: dict, *keys: str) -> dict:
    for key in keys:
        candidate = data.get(key)
        if isinstance(candidate, dict):
            return candidate
    return data


def first_list(data: dict, *keys: str) -> list:
    for key in keys:
        candidate = data.get(key)
        if isinstance(candidate, list):
            return candidate
    return []


def pick(data: dict, *keys: str):
    for key in keys:
        if key in data and data[key] not in ("", []):
            return data[key]
    return None


def normalize_tiers(raw_tiers: list, default_currency: str | None) -> list[dict]:
    normalized: list[dict] = []
    for tier in raw_tiers:
        if not isinstance(tier, dict):
            continue
        qty = pick(tier, "qty", "startNumber", "minQty", "ladder")
        price = pick(tier, "price", "productPrice", "usdPrice", "value")
        currency = pick(tier, "currency", "currencyCode") or default_currency
        try:
            qty = int(qty) if qty is not None else None
        except (TypeError, ValueError):
            qty = None
        try:
            price = float(price) if price is not None else None
        except (TypeError, ValueError):
            price = None
        normalized.append({"qty": qty, "price": price, "currency": currency})
    return normalized


def parse_json_object(payload: str) -> dict:
    parsed = json.loads(payload)
    if isinstance(parsed, dict):
        return parsed
    raise LcscApiError("Unexpected non-object JSON response")
