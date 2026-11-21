import unittest
import tkinter as tk
from pathlib import Path
from nexus_quotecheck.ui import QuoteCheckApp


class UITests(unittest.TestCase):
    def test_ui_starts_if_display_available(self):
        try:
            root = QuoteCheckApp()
        except tk.TclError:
            self.skipTest("No graphical display")
        try:
            self.assertIn("NEXUS QuoteCheck", root.title())
            self.assertEqual(root.model_var.get(), "qwen2.5:3b")
            self.assertEqual(root.project.offers, [])
        finally:
            root.destroy()

    def test_demo_flow_if_display_available(self):
        try:
            root = QuoteCheckApp()
        except tk.TclError:
            self.skipTest("No graphical display")
        try:
            root._load_demo()
            self.assertEqual(len(root.project.offers), 3)
            for off in root.project.offers:
                for item in off.items:
                    item.approved = True
            from nexus_quotecheck.matching import exact_matches
            self.assertEqual(exact_matches(root.project), 7)
            root._compare()
            self.assertEqual([o.status for o in root.result.results], ["COMPLETE", "COMPLETE", "INCOMPLETE"])
            self.assertEqual(str(root.result.results[1].total_net), "908.00")
        finally:
            root.destroy()
