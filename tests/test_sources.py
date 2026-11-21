import unittest
from pathlib import Path
from nexus_quotecheck.sources import import_offer, locate_header, parse_rows

DEMO = Path(__file__).resolve().parent.parent / "samples"


class SourceTests(unittest.TestCase):
    def test_excel_alpha(self):
        off, warn = import_offer(DEMO / "Supplier_Alpha.xlsx")
        self.assertEqual(len(off.items), 4)
        self.assertEqual(str(off.items[0].qty), "100")
        self.assertEqual(off.items[0].unit, "m")
        self.assertFalse(off.items[0].approved)

    def test_excel_beta(self):
        off, _ = import_offer(DEMO / "Supplier_Beta.xlsx")
        self.assertEqual(len(off.items), 4)
        self.assertEqual(off.items[-1].description, "Junction box IP65")

    def test_pdf_gamma(self):
        off, warnings = import_offer(DEMO / "Supplier_Gamma.pdf")
        self.assertEqual(len(off.items), 3)
        self.assertIn("Cable 3x2.5", off.raw_text)

    def test_reject_zip(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "something.zip"
            path.write_bytes(b"not an excel")
            with self.assertRaises(ValueError): import_offer(path)

    def test_detect_headers(self):
        h = locate_header(["Product", "Qty", "Unit", "Unit Price", "Total"])
        self.assertEqual(h["description"], 0)
        self.assertEqual(h["qty"], 1)
        self.assertEqual(h["unit_price"], 3)

    def test_parse_source_issues(self):
        rows = [["Item", "Qty", "Unit", "Unit Price"], ["Item A", "", "pcs", "12"]]
        items, _ = parse_rows(rows, "synthetic")
        self.assertIn("missing quantity", items[0].issues())

    def test_bad_header(self):
        items, warnings = parse_rows([["foo", "bar"]], "synthetic")
        self.assertFalse(items)
        self.assertTrue(warnings)

    def test_invoice_total_skipped(self):
        rows = [["Item", "Qty", "Unit", "Price"], ["Total", 1, "pcs", 300]]
        items, _ = parse_rows(rows, "synthetic")
        self.assertFalse(items)

    def test_source_file_unmodified(self):
        p = DEMO / "Supplier_Gamma.pdf"
        original = p.read_bytes()
        import_offer(p)
        self.assertEqual(p.read_bytes(), original)
