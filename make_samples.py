"""Recreate deterministic synthetic supplier quotation samples for the demo."""
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

ROOT = Path(__file__).resolve().parent / "samples"
ROOT.mkdir(parents=True, exist_ok=True)


def make_pdf():
    file = ROOT / "Supplier_Gamma.pdf"
    c = canvas.Canvas(str(file), pagesize=A4)
    c.setTitle("Example quotation — fictional supplier Gamma")
    c.setFillColorRGB(.16, .12, .28)
    c.rect(0, A4[1]-110, A4[0], 110, fill=1, stroke=0)
    c.setFillColorRGB(1,1,1)
    c.setFont("Helvetica-Bold", 21)
    c.drawString(42, A4[1]-65, "SUPPLIER GAMMA — QUOTATION")
    c.setFillColorRGB(.14,.16,.25)
    c.setFont("Helvetica", 10)
    c.drawString(42, A4[1]-140, "DEMO DOCUMENT ONLY — FICTIONAL SUPPLIER / NOT A REAL OFFER")
    c.drawString(42, A4[1]-162, "Currency: RON    Price type: NET (EXCLUDING VAT)")
    c.drawString(42, A4[1]-184, "IMPORTANT: Junction box is missing in this quote.")
    rows = [
        "Item | Quantity | Unit | Unit Price | Line Total",
        "Cable 3x2.5 mm2 | 100 | m | 4.05 | 405.00",
        "PVC conduit 20 mm | 60 | m | 2.05 | 123.00",
        "Circuit breaker C16 | 10 | pcs | 22.50 | 225.00",
    ]
    c.setFont("Courier", 9)
    for idx, row in enumerate(rows):
        c.drawString(42, A4[1] - 235 - idx*26, row)
    c.setStrokeColorRGB(.76,.72,.86)
    c.line(42, A4[1] - 250, 540, A4[1] - 250)
    c.setFont("Helvetica", 9)
    c.drawString(42, 100, "Not accounting, tax or purchase advice. Use only to test NEXUS QuoteCheck AI.")
    c.save()
    return file

if __name__ == "__main__":
    print(make_pdf())
