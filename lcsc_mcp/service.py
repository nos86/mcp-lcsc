from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .cache import load_json_if_fresh, save_json
from .client import LcscApiError, LcscClient, first_dict, first_list, normalize_tiers, pick, utc_now_iso
from .config import Settings
from .models import (
    ComponentResult,
    DownloadDatasheetResult,
    ReadDatasheetResult,
    SearchComponentsResult,
    SearchDatasheetResult,
)
from .pdf_tools import parse_pages, read_pdf_pages, render_markdown, search_in_pages


class LcscService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _market_cache_path(self, prefix: str, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.settings.cache_dir / "market" / f"{prefix}-{digest}.json"

    @staticmethod
    def _validate_lcsc_id(lcsc_id: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", lcsc_id):
            raise LcscApiError("Invalid lcsc_id format")
        return lcsc_id

    def _text_cache_path(self, lcsc_id: str) -> Path:
        return self.settings.cache_dir / "text" / f"{lcsc_id}.json"

    def _pdf_meta_path(self, lcsc_id: str) -> Path:
        return self.settings.cache_dir / "pdf" / f"{lcsc_id}.meta.json"

    def _load_text_cache(self, lcsc_id: str) -> dict[int, str]:
        path = self._text_cache_path(lcsc_id)
        if not path.exists():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        out: dict[int, str] = {}
        for key, value in payload.items():
            try:
                out[int(key)] = str(value)
            except (TypeError, ValueError):
                continue
        return out

    def _save_text_cache(self, lcsc_id: str, pages: dict[int, str]) -> None:
        path = self._text_cache_path(lcsc_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {str(k): v for k, v in pages.items()}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    async def search_components(self, query: str, limit: int = 10, in_stock_only: bool = False, basic_only: bool = False) -> dict:
        key = f"{query}|{limit}|{in_stock_only}|{basic_only}"
        cache_path = self._market_cache_path("search", key)
        cached = load_json_if_fresh(cache_path, self.settings.market_cache_ttl_seconds)
        if cached:
            return cached

        async with LcscClient(self.settings) as client:
            payload, source_url = await client.search(query=query, limit=limit, in_stock_only=in_stock_only, basic_only=basic_only)
        data = first_dict(payload, "result", "data")
        items = first_list(data, "productSearchResultVO", "list", "items", "rows")
        if not items and isinstance(payload.get("result"), dict):
            nested_data = payload["result"].get("data")
            if isinstance(nested_data, dict):
                nested_items = nested_data.get("items")
                if isinstance(nested_items, list):
                    items = nested_items

        parsed_items: list[dict] = []
        for raw in items[:limit]:
            if not isinstance(raw, dict):
                continue
            tiers = normalize_tiers(first_list(raw, "priceList", "productPriceList", "ladderPriceList"), self.settings.preferred_currency)
            first_tier = tiers[0]["price"] if tiers else None
            parsed_items.append(
                {
                    "lcsc_id": pick(raw, "productCode", "componentCode", "lcscPart", "partNumber"),
                    "mpn": pick(raw, "productModel", "mpn", "model"),
                    "manufacturer": pick(raw, "brandNameEn", "manufacturer", "brandName"),
                    "description": pick(raw, "productDescEn", "description", "title"),
                    "package": pick(raw, "encapStandard", "package", "pkg"),
                    "first_tier_unit_price": first_tier,
                    "stock": pick(raw, "stockNumber", "stock", "productNumber"),
                    "page_url": pick(raw, "url", "productUrl") or (
                        f"https://www.lcsc.com/product-detail/{pick(raw, 'productCode', 'componentCode', 'lcscPart')}.html"
                        if pick(raw, "productCode", "componentCode", "lcscPart")
                        else None
                    ),
                }
            )

        result = SearchComponentsResult(items=parsed_items, source_url=source_url, fetched_at=utc_now_iso()).model_dump()
        save_json(cache_path, result)
        return result

    async def get_component(self, lcsc_id: str) -> dict:
        lcsc_id = self._validate_lcsc_id(lcsc_id)
        cache_path = self._market_cache_path("component", lcsc_id)
        cached = load_json_if_fresh(cache_path, self.settings.market_cache_ttl_seconds)
        if cached:
            return cached

        async with LcscClient(self.settings) as client:
            payload, source_url = await client.component(lcsc_id)

        data = first_dict(payload, "result", "data")
        detail = first_dict(data, "productDetail", "component", "product")

        if not detail:
            raise LcscApiError(f"Component {lcsc_id} not found")

        parameters = {}
        param_items = first_list(detail, "paramVOList", "productParams", "params")
        for row in param_items:
            if not isinstance(row, dict):
                continue
            name = pick(row, "paramNameEn", "paramName", "name")
            value = pick(row, "paramValueEn", "paramValue", "value")
            if name:
                parameters[str(name)] = None if value is None else str(value)

        tiers = normalize_tiers(first_list(detail, "productPriceList", "priceList", "ladderPriceList"), self.settings.preferred_currency)

        result = ComponentResult(
            lcsc_id=pick(detail, "productCode", "componentCode", "lcscPart") or lcsc_id,
            mpn=pick(detail, "productModel", "mpn", "model"),
            manufacturer=pick(detail, "brandNameEn", "brandName", "manufacturer"),
            category=pick(detail, "parentCatalogName", "catalogName", "categoryName"),
            description=pick(detail, "productDescEn", "description", "title"),
            package=pick(detail, "encapStandard", "package", "pkg"),
            parameters=parameters,
            price_tiers=tiers,
            stock=pick(detail, "stockNumber", "stock", "productNumber"),
            moq=pick(detail, "moq", "minBuyNumber", "minQty"),
            order_multiple=pick(detail, "orderMultiple", "multiple"),
            basic_extended=pick(detail, "productArrange", "basicExtended", "attribute"),
            page_url=pick(detail, "url", "productUrl") or f"https://www.lcsc.com/product-detail/{lcsc_id}.html",
            datasheet_url=pick(detail, "datasheetUrl", "pdfUrl"),
            source_url=source_url,
            fetched_at=utc_now_iso(),
        ).model_dump()

        save_json(cache_path, result)
        return result

    async def download_datasheet(self, lcsc_id: str) -> dict:
        lcsc_id = self._validate_lcsc_id(lcsc_id)
        component = await self.get_component(lcsc_id)
        datasheet_url = component.get("datasheet_url")
        if not datasheet_url:
            raise LcscApiError(f"Datasheet URL not available for {lcsc_id}")

        pdf_path = self.settings.cache_dir / "pdf" / f"{lcsc_id}.pdf"
        source_url = str(datasheet_url)
        meta_path = self._pdf_meta_path(lcsc_id)
        sha256: str
        size_bytes: int
        cached_meta = None
        if meta_path.exists():
            cached_meta = json.loads(meta_path.read_text(encoding="utf-8"))

        if (not pdf_path.exists()) or (not cached_meta) or (cached_meta.get("source_url") != source_url):
            async with LcscClient(self.settings) as client:
                sha256, size_bytes = await client.download_pdf(
                    lcsc_id=lcsc_id, datasheet_url=str(datasheet_url), destination=pdf_path
                )
            meta_path.parent.mkdir(parents=True, exist_ok=True)
            meta_path.write_text(
                json.dumps({"source_url": source_url, "sha256": sha256, "size_bytes": size_bytes}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        else:
            if cached_meta and cached_meta.get("sha256") and cached_meta.get("size_bytes") is not None:
                sha256 = str(cached_meta["sha256"])
                size_bytes = int(cached_meta["size_bytes"])
            else:
                size_bytes = pdf_path.stat().st_size
                hasher = hashlib.sha256()
                with pdf_path.open("rb") as f:
                    for chunk in iter(lambda: f.read(8192), b""):
                        hasher.update(chunk)
                sha256 = hasher.hexdigest()

        page_count = None
        try:
            import pdfplumber

            with pdfplumber.open(str(pdf_path)) as pdf:
                page_count = len(pdf.pages)
        except Exception:
            page_count = None

        return DownloadDatasheetResult(
            lcsc_id=lcsc_id,
            path=str(pdf_path),
            sha256=sha256,
            size_bytes=size_bytes,
            page_count=page_count,
            source_url=source_url,
            fetched_at=utc_now_iso(),
        ).model_dump()

    async def read_datasheet(self, lcsc_id: str, pages: str = "1-5", max_chars: int = 30000) -> dict:
        lcsc_id = self._validate_lcsc_id(lcsc_id)
        download = await self.download_datasheet(lcsc_id)
        pdf_path = Path(download["path"])

        page_count = int(download.get("page_count") or 0)
        if page_count <= 0:
            _, detected_page_count = read_pdf_pages(pdf_path, [1])
            page_count = detected_page_count

        selected_pages = parse_pages(pages, page_count)
        cached = self._load_text_cache(lcsc_id)
        missing = [page for page in selected_pages if page not in cached]
        if missing:
            page_text, _ = read_pdf_pages(pdf_path, missing)
            cached.update(page_text)
            self._save_text_cache(lcsc_id, cached)
        selected_text = {page: cached.get(page, "") for page in selected_pages}

        markdown, truncated, resume_from, needs_ocr = render_markdown(selected_text, max_chars=max_chars)
        return ReadDatasheetResult(
            lcsc_id=lcsc_id,
            markdown=markdown,
            truncated=truncated,
            resume_from_page=resume_from,
            needs_ocr=needs_ocr,
            source_url=download["source_url"],
            fetched_at=utc_now_iso(),
        ).model_dump()

    async def search_datasheet(self, lcsc_id: str, query: str, context_lines: int = 3) -> dict:
        lcsc_id = self._validate_lcsc_id(lcsc_id)
        download = await self.download_datasheet(lcsc_id)
        pdf_path = Path(download["path"])

        page_count = int(download.get("page_count") or 0)
        if page_count <= 0:
            _, page_count = read_pdf_pages(pdf_path, [1])

        all_pages = list(range(1, page_count + 1))
        cached = self._load_text_cache(lcsc_id)
        missing = [page for page in all_pages if page not in cached]
        if missing:
            page_text, _ = read_pdf_pages(pdf_path, missing)
            cached.update(page_text)
            self._save_text_cache(lcsc_id, cached)
        matches, regex_mode = search_in_pages(cached, query=query, context_lines=context_lines)

        return SearchDatasheetResult(
            lcsc_id=lcsc_id,
            query=query,
            regex=regex_mode,
            matches=matches,
            source_url=download["source_url"],
            fetched_at=utc_now_iso(),
        ).model_dump()
