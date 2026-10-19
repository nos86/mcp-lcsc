from __future__ import annotations

from pydantic import BaseModel, Field


class PriceTier(BaseModel):
    qty: int | None
    price: float | None
    currency: str | None


class SearchComponentItem(BaseModel):
    lcsc_id: str | None
    mpn: str | None
    manufacturer: str | None
    description: str | None
    package: str | None
    first_tier_unit_price: float | None
    stock: int | None
    page_url: str | None


class SearchComponentsResult(BaseModel):
    items: list[SearchComponentItem]
    source_url: str
    fetched_at: str


class ComponentResult(BaseModel):
    lcsc_id: str | None
    mpn: str | None
    manufacturer: str | None
    category: str | None
    description: str | None
    package: str | None
    packaging: str | None
    parameters: dict[str, str | None] = Field(default_factory=dict)
    price_tiers: list[PriceTier] = Field(default_factory=list)
    stock: int | None
    moq: int | None
    order_multiple: int | None
    max_order_qty: int | None
    basic_extended: str | None
    page_url: str | None
    datasheet_url: str | None
    source_url: str
    fetched_at: str


class DownloadDatasheetResult(BaseModel):
    lcsc_id: str
    path: str
    sha256: str
    size_bytes: int
    page_count: int | None
    source_url: str
    fetched_at: str


class ReadDatasheetResult(BaseModel):
    lcsc_id: str
    markdown: str
    truncated: bool
    resume_from_page: int | None
    needs_ocr: bool
    empty_pages: list[int] = Field(default_factory=list)
    source_url: str
    fetched_at: str


class DatasheetHit(BaseModel):
    page: int
    context: str


class SearchDatasheetResult(BaseModel):
    lcsc_id: str
    query: str
    regex: bool
    matches: list[DatasheetHit]
    total_matches: int
    truncated: bool
    page_range: str | None = None
    source_url: str
    fetched_at: str

