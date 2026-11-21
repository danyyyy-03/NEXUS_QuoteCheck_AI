import unittest
from unittest.mock import patch
from nexus_quotecheck.ollama_client import validate_ai_items, extract_items, suggest_mappings, OllamaError
from nexus_quotecheck.models import Offer, Item


class OllamaTests(unittest.TestCase):
    def test_valid_extraction_unapproved(self):
        result = {"items": [{"description": "Cable", "quantity": "5", "unit": "m", "unit_price": "2.5", "line_total": "12.5", "evidence": "Cable | 5 | m | 2.5 | 12.5"}]}
        items, warnings = validate_ai_items(result, "Cable | 5 | m | 2.5 | 12.5", "PDF p1")
        self.assertEqual(len(items), 1)
        self.assertFalse(items[0].approved)
        self.assertFalse(warnings)

    def test_evidence_mismatch_warns(self):
        raw = {"items": [{"description": "Cable", "quantity": "5", "unit": "m", "unit_price": "2", "line_total": None, "evidence": "Imaginary"}]}
        items, warnings = validate_ai_items(raw, "Cable x", "document")
        self.assertTrue(warnings)
        self.assertFalse(items[0].approved)

    def test_reject_invalid_numbers(self):
        raw = {"items": [{"description": "Cable", "quantity": "NaN", "unit": "m", "unit_price": "2", "line_total": None, "evidence": "Cable"}]}
        items, warnings = validate_ai_items(raw, "Cable", "document")
        self.assertFalse(items)
        self.assertTrue(warnings)

    def test_reject_missing_array(self):
        with self.assertRaises(OllamaError): validate_ai_items({"wrong": []}, "", "x")

    def test_extract_mock(self):
        off = Offer("Test", source_path="offer.pdf", raw_text="Item | Quantity | Unit | Unit Price\nCable | 3 | m | 5")
        with patch("nexus_quotecheck.ollama_client.local_chat") as chat:
            chat.return_value = {"items": [{"description": "Cable", "quantity": "3", "unit": "m", "unit_price": "5", "line_total": None, "evidence": "Cable | 3 | m | 5"}]}
            rows, _ = extract_items(off, "fake:3b")
        self.assertEqual(len(rows), 1)
        self.assertEqual(str(rows[0].qty), "3")
        self.assertFalse(rows[0].approved)

    def test_empty_source(self):
        with self.assertRaises(OllamaError): extract_items(Offer("x"), "fake")

    def test_mapping_suggestions_no_apply(self):
        reference = Offer("A", items=[Item("Cable", 3, "m", 2)])
        offer = Offer("B", items=[Item("Electric cable", 3, "m", 1)])
        with patch("nexus_quotecheck.ollama_client.local_chat") as call:
            call.return_value = {"pairs": [{"item_id": offer.items[0].id, "reference_id": reference.items[0].id, "reason": "same cable"}]}
            pairs = suggest_mappings(offer, reference, "fake")
        self.assertEqual(len(pairs), 1)
        self.assertFalse(offer.items[0].ref_id)

    def test_mapping_rejects_unit_mismatch(self):
        reference = Offer("A", items=[Item("Cable", 3, "m", 2)])
        offer = Offer("B", items=[Item("Cable roll", 3, "roll", 1)])
        with patch("nexus_quotecheck.ollama_client.local_chat") as call:
            call.return_value = {"pairs": [{"item_id": offer.items[0].id, "reference_id": reference.items[0].id, "reason": "same"}]}
            pairs = suggest_mappings(offer, reference, "fake")
        self.assertEqual(pairs, [])
