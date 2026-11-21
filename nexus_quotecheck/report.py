"""Safe read-only reports. Never describe incomparable offers as cheaper."""
from __future__ import annotations
from pathlib import Path
from decimal import Decimal
import csv
import html
from datetime import datetime
from .compare import Comparison, OfferResult
from .models import Project


def _str(val):
    return "" if val is None else str(val)


def _safe_csv(value):
    text = _str(value)
    if text.lstrip()[:1] in ("=", "+", "-", "@"):
        return "'" + text
    return text


def export_csv(comp: Comparison, destination: Path) -> None:
    with Path(destination).open("x", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(["NEXUS QuoteCheck AI", "Quote Comparison", datetime.now().strftime("%Y-%m-%d")])
        writer.writerow(["Reference", comp.reference_supplier, "Currency", comp.currency])
        writer.writerow(["Notice", comp.headline])
        writer.writerow([])
        writer.writerow(["Supplier", "Quote Status", "Product", "Reference Qty", "Unit", "Net Unit Price", "Extended Net", "Line Status", "Note"])
        for offer in comp.results:
            for ln in offer.lines:
                writer.writerow([_safe_csv(offer.supplier), offer.status, _safe_csv(ln.description), _str(ln.qty), ln.unit,
                                 _str(ln.offered_price), _str(ln.extended_net), ln.status, _safe_csv(ln.note)])
        writer.writerow([])
        writer.writerow(["Supplier", "Status", "Total net", "Currency", "Notes"])
        for offer in comp.results:
            writer.writerow([_safe_csv(offer.supplier), offer.status, _str(offer.total_net), offer.currency, _safe_csv("; ".join(offer.messages))])
        writer.writerow(["Excluded", "Shipping, discounts, payment terms, delivery costs, warranties, equivalent product specifications and VAT invoice effects must be reviewed separately."])


def export_html(comp: Comparison, destination: Path) -> None:
    e = lambda val: html.escape(_str(val), quote=True)
    body = []
    body.append(f'<p class="sub">Reference basket: <strong>{e(comp.reference_supplier)}</strong> · {e(comp.items_count)} products · {e(comp.currency)}</p>')
    body.append(f'<section class="notice">{e(comp.headline)}</section>')
    body.append('<div class="cards">')
    for result in comp.results:
        winner = result.offer_id in comp.winner_ids
        total = f'{result.total_net:,.2f} {result.currency}' if result.total_net is not None else 'NOT RANKED'
        body.append(f'<div class="card"><div class="mini">{e(result.status)} {"· LOWEST VERIFIED" if winner else ""}</div>'
                    f'<h2>{e(result.supplier)}</h2><div class="amount">{e(total)}</div><p>{e("; ".join(result.messages) or "All reference products mapped and verified")}</p></div>')
    body.append('</div>')
    for result in comp.results:
        body.append(f'<h2>{e(result.supplier)} — Line audit</h2><div class="scroll"><table><thead><tr><th>Item</th><th>Reference qty</th><th>Unit</th><th>Net unit</th><th>Extended net</th><th>Status</th><th>Note</th></tr></thead><tbody>')
        for line in result.lines:
            cls = 'bad' if line.status != 'OK' else 'good'
            body.append(f'<tr><td>{e(line.description)}</td><td>{e(line.qty)}</td><td>{e(line.unit)}</td><td>{e(line.offered_price)}</td><td>{e(line.extended_net)}</td><td class="{cls}">{e(line.status)}</td><td>{e(line.note)}</td></tr>')
        body.append('</tbody></table></div>')
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    output = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NEXUS QuoteCheck AI — Comparison</title><style>
    :root{font-family:Inter,Segoe UI,Arial,sans-serif;color:#edeef7;background:#10121b}body{max-width:1150px;margin:0 auto;padding:36px 24px}header{display:flex;align-items:baseline;gap:14px}h1{font-size:30px;margin:0}h2{font-size:18px}.purple{color:#a78bfa}.sub{color:#a8aec3}.notice{border:1px solid #484060;background:#221c36;padding:16px;border-radius:12px;line-height:1.6}.cards{display:flex;flex-wrap:wrap;gap:14px;margin:25px 0}.card{background:#1d2130;border:1px solid #31354b;border-radius:12px;padding:16px;flex:1;min-width:220px}.mini{color:#bba9ff;font-weight:600;font-size:11px}.amount{font-weight:800;font-size:21px}.card p{font-size:12px;color:#aeb4c8;line-height:1.5}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;margin-bottom:30px;background:#1b1f2b}th{text-align:left;background:#252a3c;color:#d9d9eb;font-size:12px}td,th{padding:11px;border-bottom:1px solid #353a4a;font-size:12px}td{color:#dfe0eb}.bad{color:#ffbc91}.good{color:#78e3c4}footer{border-top:1px solid #303448;padding-top:15px;color:#9ca3b7;font-size:12px;line-height:1.6}@media print{:root{color:#111;background:#fff}.card,table,.notice{background:#fff;color:#111}td{color:#111}}
    </style></head><body><header><h1><span class="purple">NEXUS</span> QuoteCheck AI</h1><small class="sub">QUOTE COMPARISON / ''' + e(now) + '''</small></header>''' + '\n'.join(body) + '''<footer>Independent deterministic calculations. Review invoices, specification equivalence, taxes, freight, guarantees, terms and original documents. AI-extracted values must be manually verified. Incomplete offers are not ranked.</footer></body></html>'''
    Path(destination).write_text(output, encoding="utf-8", errors="strict")


def _safe_excel(value):
    """Force untrusted spreadsheet text to stay plain text (no formula injection)."""
    if isinstance(value, str) and value.lstrip()[:1] in ("=", "+", "-", "@"):
        return "'" + value
    return value


def export_xlsx(comp: Comparison, destination: Path) -> None:
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter
    except ImportError as exc:
        raise RuntimeError("openpyxl is missing") from exc
    wb = Workbook()
    overview = wb.active
    overview.title = "Overview"
    overview.append(["NEXUS QuoteCheck AI", "Supplier comparison — net material cost"])
    overview.append(["Reference offer", _safe_excel(comp.reference_supplier)])
    overview.append(["Currency", comp.currency])
    overview.append(["Items in basket", comp.items_count])
    overview.append(["Decision note", _safe_excel(comp.headline)])
    overview.append([])
    overview.append(["Supplier", "Status", "Net material total", "Currency", "Warnings"])
    for result in comp.results:
        overview.append([_safe_excel(result.supplier), result.status, float(result.total_net) if result.total_net is not None else None, result.currency, _safe_excel("; ".join(result.messages))])
    overview.append([])
    overview.append(["Exclusions", "Shipping, discounts, payment terms, specifications, contract risks not assessed."])
    detail = wb.create_sheet("Line Audit")
    detail.append(["Supplier", "Offer status", "Material", "Reference qty", "Unit", "Net unit price", "Extended net", "Line status", "Notes"])
    for result in comp.results:
        for line in result.lines:
            detail.append([_safe_excel(result.supplier), result.status, _safe_excel(line.description), float(line.qty), line.unit,
                           float(line.offered_price) if line.offered_price is not None else None,
                           float(line.extended_net) if line.extended_net is not None else None, line.status, _safe_excel(line.note)])
    for sheet in (overview, detail):
        sheet.freeze_panes = "A8" if sheet == overview else "A2"
        sheet.sheet_view.showGridLines = False
        sheet.column_dimensions["A"].width = 27
        widths = [27, 25, 39, 18, 12, 19, 21, 20, 57]
        for col, width in enumerate(widths[:9], 1):
            sheet.column_dimensions[get_column_letter(col)].width = width
        header_row = 7 if sheet == overview else 1
        for cell in sheet[header_row]:
            cell.fill = PatternFill("solid", fgColor="302451")
            cell.font = Font(name="Aptos", size=10, color="FFFFFF", bold=True)
            cell.alignment = Alignment(wrap_text=True)
        sheet.row_dimensions[header_row].height = 28
        for row in sheet.iter_rows(min_row=header_row + 1):
            for cell in row:
                cell.alignment = Alignment(vertical="center", wrap_text=True)
        for row in range(header_row + 1, sheet.max_row + 1):
            if row % 2 == 0:
                for cell in sheet[row]:
                    cell.fill = PatternFill("solid", fgColor="F3F0FA")
    for cell in overview[1]:
        cell.font = Font(name="Aptos Display", size=19, bold=True, color="6C43B0")
    for row in range(8, overview.max_row + 1):
        overview.cell(row, 3).number_format = '#,##0.00'
    for row in range(2, detail.max_row + 1):
        for col in (6, 7):
            detail.cell(row, col).number_format = '#,##0.00'
    wb.save(str(destination))
