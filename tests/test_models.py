import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from nexus_quotecheck.models import Item, Offer, Project, parse_decimal, normalize_unit


class ModelTests(unittest.TestCase):
    def test_decimal_eu(self):
        self.assertEqual(parse_decimal("4,25"), Decimal("4.25"))

    def test_decimal_us(self):
        self.assertEqual(parse_decimal("1,234.56"), Decimal("1234.56"))

    def test_decimal_european_thousands(self):
        self.assertEqual(parse_decimal("1.234,56"), Decimal("1234.56"))

    def test_none(self):
        self.assertIsNone(parse_decimal(""))

    def test_reject_nan(self):
        with self.assertRaises(ValueError): parse_decimal("NaN")

    def test_reject_infinite(self):
        with self.assertRaises(ValueError): parse_decimal("Infinity")

    def test_reject_ambiguous(self):
        with self.assertRaises(ValueError): parse_decimal("1,2,3")

    def test_normalize_unit(self):
        self.assertEqual(normalize_unit("buc."), "pcs")
        self.assertEqual(normalize_unit("metres"), "m")

    def test_item_missing_price(self):
        it = Item("a", 3, "pcs", None)
        self.assertIn("missing unit price", it.issues())

    def test_item_mismatch(self):
        it = Item("a", 3, "pcs", "4", "18")
        self.assertIn("line total differs from quantity × unit price", it.issues())

    def test_ready_requires_approval(self):
        it = Item("a", 3, "pcs", "4")
        self.assertFalse(it.ready())
        it.approved = True
        self.assertTrue(it.ready())

    def test_negative_price(self):
        with self.assertRaises(ValueError): Item("a", 2, "pcs", "-2")

    def test_zero_qty(self):
        with self.assertRaises(ValueError): Item("a", 0, "pcs", "2")

    def test_invalid_vat(self):
        with self.assertRaises(ValueError): Offer("supplier", vat_rate=101)

    def test_invalid_currency(self):
        with self.assertRaises(ValueError): Offer("supplier", currency="BTC")

    def test_roundtrip(self):
        item = Item("test", "4", "pcs", "5.30", approved=True)
        off = Offer("O", items=[item])
        project = Project(offers=[off], reference_id=off.id)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "test.nqc.json"
            project.save(path)
            result = Project.load(path)
        self.assertEqual(result.offers[0].items[0].unit_price, Decimal("5.30"))
        self.assertEqual(result.reference_id, off.id)

    def test_wrong_project(self):
        with self.assertRaises(ValueError): Project.from_dict({"format": "wrong", "version": 1})
