from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

from .client import LcscApiError
from .config import Settings
from .service import LcscService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = Settings.from_env()
service = LcscService(settings)
mcp = FastMCP("lcsc-mcp")


@mcp.tool()
async def search_components(query: str, limit: int = 10, in_stock_only: bool = False, basic_only: bool = False) -> dict:
    try:
        return await service.search_components(query=query, limit=limit, in_stock_only=in_stock_only, basic_only=basic_only)
    except Exception as exc:  # pragma: no cover
        logger.exception("search_components failed")
        raise LcscApiError(f"search_components error: {exc}") from exc


@mcp.tool()
async def get_component(lcsc_id: str) -> dict:
    try:
        return await service.get_component(lcsc_id=lcsc_id)
    except Exception as exc:  # pragma: no cover
        logger.exception("get_component failed")
        raise LcscApiError(f"get_component error: {exc}") from exc


@mcp.tool()
async def download_datasheet(lcsc_id: str) -> dict:
    try:
        return await service.download_datasheet(lcsc_id=lcsc_id)
    except Exception as exc:  # pragma: no cover
        logger.exception("download_datasheet failed")
        raise LcscApiError(f"download_datasheet error: {exc}") from exc


@mcp.tool()
async def read_datasheet(lcsc_id: str, pages: str = "1-5", max_chars: int = 30000) -> dict:
    try:
        return await service.read_datasheet(lcsc_id=lcsc_id, pages=pages, max_chars=max_chars)
    except Exception as exc:  # pragma: no cover
        logger.exception("read_datasheet failed")
        raise LcscApiError(f"read_datasheet error: {exc}") from exc


@mcp.tool()
async def search_datasheet(lcsc_id: str, query: str, context_lines: int = 3) -> dict:
    try:
        return await service.search_datasheet(lcsc_id=lcsc_id, query=query, context_lines=context_lines)
    except Exception as exc:  # pragma: no cover
        logger.exception("search_datasheet failed")
        raise LcscApiError(f"search_datasheet error: {exc}") from exc
