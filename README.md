# mcp-lcsc

Server MCP (transport `stdio`) per cercare componenti LCSC, leggere metadata prodotto e interrogare datasheet PDF in modo ottimizzato per LLM.

## Requisiti
- Python 3.11+
- `uv`

## Installazione
```bash
uv sync
```

## Avvio
```bash
uv run lcsc-mcp
```

## Configurazione ambiente
- `LCSC_MCP_CACHE_DIR` (default `~/.cache/lcsc-mcp`)
- `LCSC_MCP_CURRENCY` (default `USD`)
- `LCSC_MCP_PLAYWRIGHT_FALLBACK` (default `false`)
- `LCSC_MCP_REQ_PER_SEC` (default `1.5`)
- `LCSC_MCP_MARKET_TTL_SECONDS` (default `600`)
- `LCSC_MCP_MAX_PDF_SIZE_BYTES` (default `52428800`)
- `LCSC_MCP_USER_AGENT` (default `lcsc-mcp/0.1 (+https://github.com/nos86/mcp-lcsc)`)

## Tool esposti
- `search_components(query, limit=10, in_stock_only=false, basic_only=false)`
- `get_component(lcsc_id)`
- `download_datasheet(lcsc_id)`
- `read_datasheet(lcsc_id, pages="1-5", max_chars=30000)`
- `search_datasheet(lcsc_id, query, context_lines=3)`

## Esempio Claude Code (`.mcp.json`)
```json
{
  "mcpServers": {
    "lcsc": {
      "command": "uv",
      "args": ["run", "lcsc-mcp"],
      "cwd": "/absolute/path/to/mcp-lcsc"
    }
  }
}
```

## Note importanti
- Cache prezzi/stock max 10 minuti.
- Download PDF consentito solo da host LCSC/CDN noti, solo HTTPS, max 50MB, header `%PDF` obbligatorio.
- Se il PDF non contiene testo estraibile: `needs_ocr: true`.
- Logging su `stderr` (mai su `stdout`).

## Limiti noti
- Gli endpoint LCSC documentati in `docs/endpoints.md` devono essere verificati con cattura rete reale quando il dominio è raggiungibile.
- Se LCSC cambia schema JSON/HTML o protezioni anti-bot, il parsing può rompersi e richiedere aggiornamenti.
