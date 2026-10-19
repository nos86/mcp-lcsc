from __future__ import annotations

import re
from pathlib import Path


def parse_pages(pages: str, page_count: int) -> list[int]:
    selected: set[int] = set()
    for token in pages.split(","):
        token = token.strip()
        if not token:
            continue
        if "-" in token:
            start_s, end_s = token.split("-", 1)
            start = int(start_s)
            end = int(end_s)
            for page in range(start, end + 1):
                if 1 <= page <= page_count:
                    selected.add(page)
        else:
            page = int(token)
            if 1 <= page <= page_count:
                selected.add(page)
    if not selected:
        raise ValueError("Requested page selection is empty or out of range")
    return sorted(selected)


def read_pdf_pages(pdf_path: Path, pages: list[int]) -> tuple[dict[int, str], int]:
    page_text: dict[int, str] = {}
    page_count = 0

    try:
        import pdfplumber  # fallback-ready reader and page counter
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("pdfplumber is required to read datasheets") from exc

    with pdfplumber.open(str(pdf_path)) as pdf:
        page_count = len(pdf.pages)
        for page_no in pages:
            text = ""
            if 1 <= page_no <= page_count:
                text = pdf.pages[page_no - 1].extract_text() or ""
            page_text[page_no] = text.strip()

    if any(page_text.values()):
        try:
            import pymupdf4llm

            for page_no in pages:
                md = pymupdf4llm.to_markdown(str(pdf_path), pages=[page_no - 1])
                if isinstance(md, str) and md.strip():
                    page_text[page_no] = md.strip()
        except Exception:
            pass

    return page_text, page_count


def render_markdown(page_text: dict[int, str], max_chars: int) -> tuple[str, bool, int | None, bool]:
    chunks: list[str] = []
    truncated = False
    resume_from: int | None = None

    for page_no in sorted(page_text):
        body = page_text[page_no]
        chunks.append(f"## Pagina {page_no}\n\n{body}\n")

    full_markdown = "\n".join(chunks).strip()
    needs_ocr = all(not (text or "").strip() for text in page_text.values())

    if len(full_markdown) <= max_chars:
        return full_markdown, False, None, needs_ocr

    truncated = True
    cut = full_markdown[:max_chars]

    for page_no in sorted(page_text):
        marker = f"## Pagina {page_no}"
        idx = full_markdown.find(marker)
        if idx >= max_chars:
            resume_from = page_no
            break

    if resume_from is None:
        resume_from = max(page_text.keys())

    cut += f"\n\n[TRUNCATED: riprendi da pagina {resume_from}]"
    return cut, truncated, resume_from, needs_ocr


def search_in_pages(page_text: dict[int, str], query: str, context_lines: int) -> tuple[list[dict], bool]:
    regex_mode = query.startswith("re:")
    pattern = query[3:] if regex_mode else re.escape(query)
    compiled = re.compile(pattern, re.IGNORECASE)

    results: list[dict] = []
    for page_no, text in page_text.items():
        if not text:
            continue
        lines = text.splitlines()
        for idx, line in enumerate(lines):
            if compiled.search(line):
                start = max(0, idx - context_lines)
                end = min(len(lines), idx + context_lines + 1)
                context = "\n".join(lines[start:end])
                results.append({"page": page_no, "context": context})

    return results, regex_mode
