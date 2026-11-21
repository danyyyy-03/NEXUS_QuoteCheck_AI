"""Read common Excel supplier tables and text PDFs. No macros, external links or OCR."""
from __future__ import annotations
from pathlib import Path
import re
from typing import Any
from .models import Item, Offer, parse_decimal, normalize_unit

MAX_FILE_MB = 20
MAX_ITEMS = 1000
MAX_PDF_PAGES = 40
MAX_RAW_CHARS = 45000

HEADERS = {
    "description": ["description", "item", "item description", "product", "product name", "material", "materials", "denumire", "produs", "descriere", "articol"],
    "qty": ["quantity", "qty", "q-ty", "cantitate", "cant", "amount", "numar", "number"],
    "unit": ["unit", "uom", "um", "u.m.", "unitate", "measurement unit"],
    "unit_price": ["unit price", "unitprice", "price per unit", "price/unit", "pret unitar", "pret pe unitate", "pret/u", "price", "pret"],
    "line_total": ["line total", "amount total", "total value", "total price", "value", "valoare", "valoare totala", "total", "subtotal", "suma"],
}


def header_key(value: Any) -> str:
    raw = re.sub(r"[^a-z0-9 ]+", " ", str(value or "").strip().casefold())
    return re.sub(r"\s+", " ", raw).strip()


def locate_header(row: list) -> dict[str, int]:
    out: dict[str, int] = {}
    used = set()
    for col, value in enumerate(row):
        key = header_key(value)
        if not key:
            continue
        for target, aliases in HEADERS.items():
            if target not in out and col not in used and (key in aliases or (target in ("unit_price", "line_total") and any(key.startswith(a + " ") for a in aliases))):
                out[target] = col
                used.add(col)
                break
    return out


def parse_rows(rows: list[list], origin: str) -> tuple[list[Item], list[str]]:
    warnings = []
    found = []
    for i, row in enumerate(rows[:30]):
        cols = locate_header(row)
        if "description" in cols and ("unit_price" in cols or "line_total" in cols):
            found.append((len(cols), i, cols))
    if not found:
        return [], [f"{origin}: no recognizable table header; use AI extraction or a standard Excel template"]
    _, header_index, columns = max(found, key=lambda x: (x[0], -x[1]))
    items: list[Item] = []
    seen = False
    for lineno, row in enumerate(rows[header_index + 1:], header_index + 2):
        if len(items) >= MAX_ITEMS:
            warnings.append(f"Stopped at {MAX_ITEMS} line items")
            break
        def val(key):
            col = columns.get(key, -1)
            return row[col] if 0 <= col < len(row) else None
        desc = str(val("description") or "").strip()
        if not desc:
            if seen:
                continue
            continue
        if header_key(desc).startswith(("subtotal", "total", "grand total", "tva", "vat", "transport", "shipping", "discount")):
            continue
        seen = True
        try:
            qty = parse_decimal(val("qty"))
            unit_price = parse_decimal(val("unit_price"))
            total = parse_decimal(val("line_total"))
            if unit_price is None and qty and total is not None:
                unit_price = total / qty
            it = Item(desc, qty, val("unit") or "other", unit_price, total, source_ref=f"{origin}: row {lineno}", note="Review against original; Excel tables may be misaligned.")
            items.append(it)
        except ValueError as exc:
            warnings.append(f"{origin}: skipped row {lineno}: {exc}")
    if not items:
        warnings.append(f"{origin}: no valid item rows found")
    return items, warnings


def read_excel(path: Path) -> tuple[list[Item], str, list[str]]:
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise RuntimeError("openpyxl is missing. Run setup.bat.") from exc
    warnings: list[str] = []
    items: list[Item] = []
    chunks: list[str] = []
    workbook = load_workbook(str(path), read_only=True, data_only=True, keep_links=False)
    try:
        for sheet in workbook.worksheets[:8]:
            rows = []
            for index, row in enumerate(sheet.iter_rows(values_only=True)):
                if index >= 1200:
                    warnings.append(f"Sheet '{sheet.title}' truncated after 1,200 rows")
                    break
                rows.append([str(x) if x is not None else "" for x in row[:30]])
            label = f"{path.name} / {sheet.title}"
            extracted, issues = parse_rows(rows, label)
            items.extend(extracted)
            warnings.extend(issues)
            chunks.append("SHEET: " + sheet.title + "\n" + "\n".join(" | ".join(r[:12]) for r in rows[:150]))
            if len(items) >= MAX_ITEMS:
                break
    finally:
        workbook.close()
    return items[:MAX_ITEMS], "\n\n".join(chunks)[:MAX_RAW_CHARS], warnings


def read_pdf(path: Path) -> tuple[list[Item], str, list[str]]:
    try:
        import pymupdf
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is missing. Run setup.bat.") from exc
    warnings: list[str] = []
    document = pymupdf.open(str(path))
    try:
        if document.is_encrypted:
            raise ValueError("Password-protected PDFs are unsupported")
        chunks: list[str] = []
        pipe_rows: list[list[str]] = []
        for page_idx in range(min(len(document), MAX_PDF_PAGES)):
            txt = document[page_idx].get_text("text", sort=True)
            chunks.append(f"PAGE {page_idx + 1}:\n{txt}")
            for line in txt.splitlines():
                if "|" in line:
                    pipe_rows.append([c.strip() for c in line.split("|")])
        if len(document) > MAX_PDF_PAGES:
            warnings.append(f"PDF has more than {MAX_PDF_PAGES} pages; remaining pages were not read")
        raw_text = "\n\n".join(chunks)
        if not raw_text.strip():
            warnings.append("PDF contains no extractable text (possibly scanned). OCR is not included.")
        if len(raw_text) > MAX_RAW_CHARS:
            warnings.append("Long PDF was truncated to 45,000 characters for AI analysis")
        items = []
        if pipe_rows:
            items, parse_warn = parse_rows(pipe_rows, path.name + " / PDF pipe table")
            warnings.extend(parse_warn if not items else [])
        if not items:
            warnings.append("No standard pipe table detected; click Extract with Ollama, then verify every item")
        return items, raw_text[:MAX_RAW_CHARS], warnings
    finally:
        document.close()


def import_offer(path: Path) -> tuple[Offer, list[str]]:
    path = Path(path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size > MAX_FILE_MB * 1024 * 1024:
        raise ValueError(f"File exceeds {MAX_FILE_MB} MB limit")
    ext = path.suffix.lower()
    if ext == ".xlsx":
        items, raw_text, warnings = read_excel(path)
    elif ext == ".pdf":
        items, raw_text, warnings = read_pdf(path)
    else:
        raise ValueError("Supported file formats: .pdf, .xlsx")
    offer = Offer(supplier=path.stem[:120], items=items, source_path=str(path), raw_text=raw_text)
    return offer, warnings
