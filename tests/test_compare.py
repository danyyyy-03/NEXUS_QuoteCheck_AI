import unittest
from decimal import Decimal
from nexus_quotecheck.models import Offer, Project, Item, PRICE_MODES
from nexus_quotecheck.compare import compare_project
from nexus_quotecheck.matching import exact_matches, map_item, normalize_name


def make_project():
    a = Offer("Alpha", items=[Item("Cable x", 100, "m", "4.40", approved=True), Item("Breaker", 10, "pcs", 24, approved=True)])
    b = Offer("Beta", items=[Item("Cable x", 100, "m", "4.00", approved=True), Item("Breaker", 10, "pcs", 22, approved=True)])
    p = Project([a,b], a.id)
    exact_matches(p)
    return p


class ComparisonTests(unittest.TestCase):
    def test_correct_totals(self):
        p = make_project()
        c = compare_project(p)
        self.assertEqual([x.total_net for x in c.results], [Decimal("680.00"), Decimal("620.00")])
        self.assertEqual(c.winner_ids, [p.offers[1].id])

    def test_missing_product_never_ranked(self):
        p = make_project()
        p.offers[1].items.pop()
        c = compare_project(p)
        self.assertEqual(c.results[1].status, "INCOMPLETE")
        self.assertIsNone(c.results[1].total_net)
        self.assertEqual(c.winner_ids, [p.offers[0].id])
        self.assertIn("incomplete", c.headline)

    def test_unapproved_reference_blocks_everything(self):
        p = make_project()
        p.offers[0].items[0].approved = False
        c = compare_project(p)
        self.assertEqual(c.results, [])
        self.assertIn("Approve", c.headline)

    def test_unapproved_alternative_not_ranked(self):
        p = make_project()
        p.offers[1].items[0].approved = False
        c = compare_project(p)
        self.assertIsNone(c.results[1].total_net)
        self.assertTrue(any(x.status == "REVIEW" for x in c.results[1].lines))

    def test_currency_mismatch(self):
        p = make_project()
        p.offers[1].currency = "EUR"
        c = compare_project(p)
        self.assertIsNone(c.results[1].total_net)
        self.assertTrue(any("Currency" in x for x in c.results[1].messages))

    def test_vat_missing_blocks(self):
        p = make_project()
        p.offers[1].price_mode = PRICE_MODES[1]
        c = compare_project(p)
        self.assertIsNone(c.results[1].total_net)

    def test_vat_conversion(self):
        p = make_project()
        p.offers[1].price_mode = PRICE_MODES[1]
        p.offers[1].vat_rate = Decimal("10")
        for item in p.offers[1].items: item.unit_price *= Decimal("1.1")
        c = compare_project(p)
        self.assertEqual(c.results[1].total_net, Decimal("620.00"))

    def test_quantity_scales_to_reference(self):
        p = make_project()
        p.offers[1].items[0].qty = Decimal("20")
        c = compare_project(p)
        self.assertEqual(c.results[1].lines[0].qty, Decimal("100"))
        self.assertEqual(c.results[1].total_net, Decimal("620.00"))

    def test_duplicate_matches_block(self):
        p = make_project()
        p.offers[1].items.append(Item("Cable x", 100, "m", 3, approved=True, ref_id=p.offers[0].items[0].id))
        c = compare_project(p)
        self.assertEqual(c.results[1].lines[0].status, "DUPLICATE")
        self.assertIsNone(c.results[1].total_net)

    def test_unknown_unit_blocks(self):
        p = make_project()
        p.offers[1].items[0].unit = "other"
        c = compare_project(p)
        self.assertIsNone(c.results[1].total_net)

    def test_no_reference(self):
        c = compare_project(Project())
        self.assertIn("reference", c.headline.lower())

    def test_reference_duplicate_lines_no_silent_omit(self):
        p = make_project()
        p.offers[0].items.append(Item("Unknown", None, "pcs", 1))
        c = compare_project(p)
        self.assertEqual(c.results, [])

    def test_name_normalizer(self):
        self.assertEqual(normalize_name("   Cablu-PVC   "), "cablu pvc")

    def test_exact_matching_does_not_use_close_names(self):
        p = make_project()
        p.offers[1].items[0].ref_id = ""
        p.offers[1].items[0].description = "Different Cable Product"
        self.assertEqual(exact_matches(p), 0)

    def test_same_unit_required_mapping(self):
        p = make_project()
        p.offers[1].items[0].unit = "roll"
        with self.assertRaises(ValueError):
            map_item(p, p.offers[1].id, p.offers[1].items[0].id, p.offers[0].items[0].id)

    def test_tied_winners(self):
        p = make_project()
        for a, b in zip(p.offers[1].items, p.offers[0].items): a.unit_price = b.unit_price
        c = compare_project(p)
        self.assertEqual(set(c.winner_ids), {o.id for o in p.offers})
