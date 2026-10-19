from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

import pytest

from lcsc_mcp.config import Settings
from lcsc_mcp.service import LcscService


class StubClient:
    def __init__(self, settings, *_, **__):
        self.settings = settings

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def search(self, query: str, limit: int, in_stock_only: bool, basic_only: bool):
        payload = json.loads((Path(__file__).parent / "fixtures" / "search_response.json").read_text(encoding="utf-8"))
        return payload, "https://wmsc.lcsc.com/ftps/wm/search/global?keyword=NE555"

    async def component(self, lcsc_id: str):
        payload = json.loads((Path(__file__).parent / "fixtures" / "component_response.json").read_text(encoding="utf-8"))
        return payload, f"https://wmsc.lcsc.com/ftps/wm/product/detail?productCode={lcsc_id}"


@pytest.fixture
def service(tmp_path, monkeypatch):
    settings = Settings(
        cache_dir=tmp_path,
        preferred_currency="USD",
        enable_playwright_fallback=False,
        requests_per_second=100,
        market_cache_ttl_seconds=600,
        max_pdf_size_bytes=50 * 1024 * 1024,
        user_agent="test-agent",
    )

    from lcsc_mcp import service as svc_module

    monkeypatch.setattr(svc_module, "LcscClient", StubClient)
    return LcscService(settings)


@pytest.mark.asyncio
async def test_search_components(service):
    result = await service.search_components("NE555", limit=10, in_stock_only=False, basic_only=False)

    assert result["items"][0]["lcsc_id"] == "C2040"
    assert result["items"][0]["first_tier_unit_price"] == 0.12
    parsed = urlparse(result["source_url"])
    assert parsed.scheme == "https"
    assert parsed.hostname == "wmsc.lcsc.com"
    assert "fetched_at" in result


@pytest.mark.asyncio
async def test_get_component(service):
    result = await service.get_component("C2040")

    assert result["lcsc_id"] == "C2040"
    assert result["manufacturer"] == "Texas Instruments"
    assert result["parameters"]["Supply Voltage"] == "4.5V~16V"
    assert len(result["price_tiers"]) == 2
    assert result["datasheet_url"] == "https://datasheet.lcsc.com/lcsc/1234.pdf"


@pytest.mark.asyncio
async def test_get_component_rejects_invalid_id(service):
    with pytest.raises(RuntimeError, match="Invalid lcsc_id format"):
        await service.get_component("../etc/passwd")


@pytest.mark.asyncio
async def test_read_datasheet_truncation_and_ocr_flag(service, monkeypatch):
    async def fake_download(_lcsc_id: str):
        return {
            "lcsc_id": "C2040",
            "path": "/tmp/fake.pdf",
            "sha256": "x",
            "size_bytes": 100,
            "page_count": 2,
            "source_url": "https://datasheet.lcsc.com/lcsc/1234.pdf",
            "fetched_at": "2026-01-01T00:00:00+00:00",
        }

    def fake_read_pdf_pages(_pdf_path, pages):
        out = {page: ("line\n" * 200 if page == 1 else "") for page in pages}
        return out, 2

    from lcsc_mcp import service as svc_module

    monkeypatch.setattr(service, "download_datasheet", fake_download)
    monkeypatch.setattr(svc_module, "read_pdf_pages", fake_read_pdf_pages)

    result = await service.read_datasheet("C2040", pages="1-2", max_chars=300)

    assert result["truncated"] is True
    assert result["resume_from_page"] in {1, 2}
    assert "## Pagina 1" in result["markdown"]


@pytest.mark.asyncio
async def test_search_datasheet_regex(service, monkeypatch):
    async def fake_download(_lcsc_id: str):
        return {
            "lcsc_id": "C2040",
            "path": "/tmp/fake.pdf",
            "sha256": "x",
            "size_bytes": 100,
            "page_count": 1,
            "source_url": "https://datasheet.lcsc.com/lcsc/1234.pdf",
            "fetched_at": "2026-01-01T00:00:00+00:00",
        }

    def fake_read_pdf_pages(_pdf_path, pages):
        return ({1: "Absolute Maximum Ratings\nVCC must be <= 16V"}, 1)

    from lcsc_mcp import service as svc_module

    monkeypatch.setattr(service, "download_datasheet", fake_download)
    monkeypatch.setattr(svc_module, "read_pdf_pages", fake_read_pdf_pages)

    result = await service.search_datasheet("C2040", query="re:maximum", context_lines=1)

    assert result["regex"] is True
    assert result["matches"]
    assert result["matches"][0]["page"] == 1
