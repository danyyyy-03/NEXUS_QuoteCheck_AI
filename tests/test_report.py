import csv
import tempfile
import unittest
from pathlib import Path
from nexus_quotecheck.compare import compare_project
from nexus_quotecheck.models import Project, Offer, Item
from nexus_quotecheck.matching import exact_matches
from nexus_quotecheck.report import export_csv, export_html, export_xlsx


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        a = Offer("Alpha", items=[Item("Cable", 5, "m", 2, approved=True)])
        b = Offer("Beta", items=[Item("Cable", 5, "m", 1, approved=True)])
        p = Project([a,b], a.id)
        exact_matches(p)
        self.comp = compare_project(p)

    def test_csv(self):
        path = self.path / "r.csv"
        export_csv(self.comp, path)
        content = path.read_text(encoding="utf-8-sig")
        self.assertIn("Beta", content)
        self.assertIn("5.00", content)

    def test_html(self):
        path = self.path / "r.html"
        export_html(self.comp, path)
        content = path.read_text(encoding="utf-8")
        self.assertIn("LOWEST VERIFIED", content)
        self.assertIn("Beta", content)

    def test_html_escape(self):
        self.comp.results[0].supplier = "<script>alert(1)</script>"
        path = self.path / "r.html"
        export_html(self.comp, path)
        content = path.read_text(encoding="utf-8")
        self.assertIn("&lt;script&gt;", content)
        self.assertNotIn("<script>alert", content)

    def test_excel(self):
        path = self.path / "r.xlsx"
        export_xlsx(self.comp, path)
        from openpyxl import load_workbook
        wb = load_workbook(path, read_only=True, data_only=True)
        self.assertEqual(wb["Overview"].cell(8, 1).value, "Alpha")
        self.assertEqual(wb["Overview"].cell(9, 3).value, 5)
        self.assertEqual(wb["Line Audit"].cell(3, 3).value, "Cable")
        wb.close()

    def test_excel_formula_injection(self):
        self.comp.results[0].supplier = '=HYPERLINK("https://invalid.example")'
        p = self.path / "safe.xlsx"
        export_xlsx(self.comp, p)
        from openpyxl import load_workbook
        wb = load_workbook(p)
        self.assertEqual(wb["Overview"].cell(8, 1).data_type, "s")
        self.assertTrue(wb["Overview"].cell(8, 1).value.startswith("'="))
        wb.close()

    def test_csv_formula_injection(self):
        self.comp.results[0].supplier = '=HYPERLINK("evil")'
        p = self.path / "r.csv"
        export_csv(self.comp, p)
        with p.open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))
        self.assertTrue(any("'=HYPERLINK" in cell for row in rows for cell in row))
