from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    cache_dir: Path
    preferred_currency: str
    enable_playwright_fallback: bool
    requests_per_second: float
    market_cache_ttl_seconds: int
    max_pdf_size_bytes: int
    user_agent: str

    @classmethod
    def from_env(cls) -> "Settings":
        cache_dir = Path(os.getenv("LCSC_MCP_CACHE_DIR", "~/.cache/lcsc-mcp")).expanduser()
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cls(
            cache_dir=cache_dir,
            preferred_currency=os.getenv("LCSC_MCP_CURRENCY", "USD"),
            enable_playwright_fallback=os.getenv("LCSC_MCP_PLAYWRIGHT_FALLBACK", "false").lower() in {"1", "true", "yes"},
            requests_per_second=float(os.getenv("LCSC_MCP_REQ_PER_SEC", "1.5")),
            market_cache_ttl_seconds=int(os.getenv("LCSC_MCP_MARKET_TTL_SECONDS", "600")),
            max_pdf_size_bytes=int(os.getenv("LCSC_MCP_MAX_PDF_SIZE_BYTES", str(50 * 1024 * 1024))),
            user_agent=os.getenv("LCSC_MCP_USER_AGENT", "lcsc-mcp/0.1 (+https://github.com/nos86/mcp-lcsc)"),
        )


KNOWN_PDF_HOSTS = {
    "datasheet.lcsc.com",
    "wmsc.lcsc.com",
    "lcsc.com",
    "www.lcsc.com",
}
