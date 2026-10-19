from __future__ import annotations

import re
from pathlib import Path

PAGE_HEADER_TEMPLATE = "## Page {page_no}"
TRUNCATED_TEMPLATE = "[TRUNCATED: resume from page {resume_from}]"


def parse_pages(pages: str, page_count: int) -> list[int]:
    selected: set[int] = set()
    for token in pages.split(","):
        token = token.strip()
        if not token:
            continue
        if "-" in token:
            start_s, end_s = token.split("-", 1)
            try:
                start = int(start_s)
                end = int(end_s)
            except ValueError as exc:
                raise ValueError(f"Invalid page token: {token}") from exc
            for page in range(start, end + 1):
                if 1 <= page <= page_count:
                    selected.add(page)
        else:
            try:
                page = int(token)
            except ValueError as exc:
                raise ValueError(f"Invalid page token: {token}") from exc
            if 1 <= page <= page_count:
                selected.add(page)
    if not selected:
        raise ValueError("Requested page selection is empty or out of range")
    return sorted(selected)


def read_pdf_pages(pdf_path: Path, pages: list[int]) -> tuple[dict[int, str], int]:
    page_text: dict[int, str] = {page_no: "" for page_no in pages}
    page_count = 0

    try:
        import pdfplumber  # fallback-ready reader and page counter
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("pdfplumber is required to read datasheets") from exc

    with pdfplumber.open(str(pdf_path)) as pdf:
        page_count = len(pdf.pages)

    try:
        import pymupdf4llm

        requested_zero_based = sorted({page_no - 1 for page_no in pages if 1 <= page_no <= page_count})
        if requested_zero_based:
            markdown_by_page = pymupdf4llm.to_markdown(str(pdf_path), pages=requested_zero_based, page_chunks=True)
            if isinstance(markdown_by_page, list):
                page_map: dict[int, str] = {}
                for chunk in markdown_by_page:
                    if not isinstance(chunk, dict):
                        continue
                    metadata = chunk.get("metadata")
                    if not isinstance(metadata, dict):
                        continue
                    page_index = metadata.get("page")
                    if page_index is None:
                        continue
                    try:
                        page_key = int(page_index)
                    except (TypeError, ValueError):
                        continue
                    text = chunk.get("text") or chunk.get("markdown") or ""
                    if not isinstance(text, str):
                        continue
                    page_map[page_key] = (page_map.get(page_key, "") + "\n" + text).strip()
                for page_no in pages:
                    if 1 <= page_no <= page_count:
                        # pymupdf4llm page_chunks output is zero-based in the current library version.
                        md = page_map.get(page_no - 1)
                        if isinstance(md, str) and md.strip():
                            page_text[page_no] = md.strip()
    except Exception:
        pass

    empty_pages = [page_no for page_no in pages if 1 <= page_no <= page_count and not (page_text.get(page_no) or "").strip()]
    if empty_pages:
        try:
            with pdfplumber.open(str(pdf_path)) as pdf:
                for page_no in empty_pages:
                    text = pdf.pages[page_no - 1].extract_text() or ""
                    if text.strip():
                        page_text[page_no] = text.strip()
        except Exception:
            pass

    return page_text, page_count


def render_markdown(page_text: dict[int, str], max_chars: int) -> tuple[str, bool, int | None, bool]:
    chunks: list[str] = []
    truncated = False
    resume_from: int | None = None

    for page_no in sorted(page_text):
        body = page_text[page_no]
        chunks.append(f"{PAGE_HEADER_TEMPLATE.format(page_no=page_no)}\n\n{body}\n")

    full_markdown = "\n".join(chunks).strip()
    needs_ocr = all(not (text or "").strip() for text in page_text.values())

    if len(full_markdown) <= max_chars:
        return full_markdown, False, None, needs_ocr

    truncated = True
    cut = full_markdown[:max_chars]

    for page_no in sorted(page_text):
        marker = PAGE_HEADER_TEMPLATE.format(page_no=page_no)
        idx = full_markdown.find(marker)
        if idx >= max_chars:
            resume_from = page_no
            break

    if resume_from is None:
        resume_from = max(page_text.keys())

    cut += f"\n\n{TRUNCATED_TEMPLATE.format(resume_from=resume_from)}"
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
