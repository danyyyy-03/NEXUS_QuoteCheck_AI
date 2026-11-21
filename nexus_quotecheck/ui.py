"""English Tkinter GUI for quotation importing, human review, and deterministic comparison."""
from __future__ import annotations
from dataclasses import replace
from pathlib import Path
from threading import Thread
import queue
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import webbrowser

from . import __version__
from .compare import Comparison, compare_project
from .matching import exact_matches, map_item
from .models import CURRENCIES, PRICE_MODES, UNITS, Item, Offer, Project, new_id
from .sources import import_offer
from .ollama_client import extract_items, installed_models, suggest_mappings, OllamaError
from .report import export_csv, export_html, export_xlsx

BG = "#10121B"
PANEL = "#1D2030"
PANEL2 = "#252A3D"
PURPLE = "#9F83F8"
TEXT = "#F2F2FC"
MUTED = "#AAB2C9"
GREEN = "#7EE3B4"
AMBER = "#FFCC87"
EDGE = "#333A50"


class QuoteCheckApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"NEXUS QuoteCheck AI  •  v{__version__}")
        self.geometry("1350x820")
        self.minsize(1090, 650)
        self.configure(background=BG)
        self.project = Project()
        self.offer_ids: list[str] = []
        self.item_ids: list[str] = []
        self.reference_ids: list[str] = []
        self.result: Comparison | None = None
        self.model_var = tk.StringVar(value="qwen2.5:3b")
        self.status_var = tk.StringVar(value="Ready — import quotations or load the demo.")
        self.supplier_var = tk.StringVar(value="")
        self.currency_var = tk.StringVar(value="RON")
        self.price_mode_var = tk.StringVar(value=PRICE_MODES[0])
        self.vat_var = tk.StringVar(value="")
        self.reference_var = tk.StringVar(value="")
        self._jobs = queue.Queue()
        self.busy = False
        self._set_style()
        self._build()
        self.after(130, self._poll)

    def _set_style(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("TNotebook", background=BG, borderwidth=0)
        s.configure("TNotebook.Tab", background=PANEL2, foreground=TEXT, padding=(20, 12), font=("Segoe UI Semibold", 10))
        s.map("TNotebook.Tab", background=[("selected", "#4D3B7A")], foreground=[("selected", "#FFFFFF")])
        s.configure("Treeview", background=PANEL, foreground=TEXT, fieldbackground=PANEL, rowheight=30, borderwidth=0, font=("Segoe UI", 9))
        s.configure("Treeview.Heading", background=PANEL2, foreground=TEXT, relief="flat", font=("Segoe UI Semibold", 9), padding=10)
        s.map("Treeview", background=[("selected", "#574487")], foreground=[("selected", TEXT)])
        s.configure("TCombobox", fieldbackground=PANEL2, background=PANEL2, foreground=TEXT, arrowcolor=TEXT, padding=5)
        s.map("TCombobox", fieldbackground=[("readonly", PANEL2)], foreground=[("readonly", TEXT)])
        s.configure("TScrollbar", background=PANEL2, troughcolor=BG)

    def _label(self, host, text, **kwargs):
        return tk.Label(host, text=text, background=kwargs.pop("background", PANEL), foreground=kwargs.pop("foreground", TEXT), font=kwargs.pop("font", ("Segoe UI", 10)), **kwargs)

    def _button(self, host, text, callback, primary=False):
        return tk.Button(host, text=text, command=callback, background=PURPLE if primary else PANEL2,
                         foreground="#141021" if primary else TEXT, relief="flat", borderwidth=0,
                         activebackground="#B5A1FF" if primary else "#434A64", activeforeground="#141021" if primary else TEXT,
                         font=("Segoe UI Semibold", 10), padx=12, pady=9, cursor="hand2")

    def _build(self):
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=21, pady=(16, 9))
        self._label(header, "NEXUS", background=BG, foreground=PURPLE, font=("Segoe UI Black", 23)).pack(side="left")
        self._label(header, "  QUOTECHECK AI", background=BG, font=("Segoe UI Semibold", 20)).pack(side="left")
        self._label(header, "LOCAL AI · VERIFIED PRICING · WINDOWS", background=BG, foreground=MUTED,
                    font=("Segoe UI", 9)).pack(side="right", pady=10)
        toolbar = tk.Frame(self, bg=BG)
        toolbar.pack(fill="x", padx=21, pady=(2, 12))
        for label, method, primary in (("Import PDF / Excel", self._import, True), ("Load Demo", self._load_demo, False),
                                        ("Open Project", self._open_project, False), ("Save Project", self._save_project, False)):
            self._button(toolbar, label, method, primary=primary).pack(side="left", padx=(0, 7))
        self._label(toolbar, "Ollama model", background=BG, foreground=MUTED).pack(side="left", padx=(25, 8))
        self.models_combo = ttk.Combobox(toolbar, textvariable=self.model_var, width=21)
        self.models_combo.pack(side="left")
        self._button(toolbar, "Refresh Models", self._refresh_models).pack(side="left", padx=7)

        area = tk.Frame(self, bg=BG)
        area.pack(fill="both", expand=True, padx=21, pady=(0, 11))
        left = tk.Frame(area, bg=PANEL, width=312, highlightthickness=1, highlightbackground=EDGE)
        left.pack(side="left", fill="y", padx=(0, 12))
        left.pack_propagate(False)
        right = tk.Frame(area, bg=BG)
        right.pack(side="left", fill="both", expand=True)

        self._label(left, "SUPPLIER QUOTES", foreground=PURPLE, font=("Segoe UI Semibold", 11)).pack(anchor="w", padx=14, pady=(15, 8))
        offers_frame = tk.Frame(left, bg=PANEL)
        offers_frame.pack(fill="both", expand=True, padx=14)
        self.offers_list = tk.Listbox(offers_frame, bg=PANEL2, fg=TEXT, relief="flat", selectbackground="#574487", selectforeground=TEXT,
                                      highlightthickness=0, borderwidth=0, activestyle="none", font=("Segoe UI", 10), exportselection=False)
        self.offers_list.pack(fill="both", expand=True)
        self.offers_list.bind("<<ListboxSelect>>", self._on_offer_selected)
        tools = tk.Frame(left, bg=PANEL)
        tools.pack(fill="x", padx=14, pady=12)
        self._button(tools, "Remove Quote", self._remove_offer).pack(side="left", fill="x", expand=True)
        self._label(left, "QUOTE SETTINGS", foreground=PURPLE, font=("Segoe UI Semibold", 11)).pack(anchor="w", padx=14, pady=(7, 7))
        form = tk.Frame(left, bg=PANEL)
        form.pack(fill="x", padx=14)
        self._label(form, "Supplier name", foreground=MUTED).pack(anchor="w")
        self.supplier_entry = tk.Entry(form, textvariable=self.supplier_var, bg=PANEL2, fg=TEXT, insertbackground=TEXT, relief="flat", font=("Segoe UI", 10))
        self.supplier_entry.pack(fill="x", ipady=7, pady=(3, 9))
        self._label(form, "Currency", foreground=MUTED).pack(anchor="w")
        self.currency_combo = ttk.Combobox(form, values=CURRENCIES, state="readonly", textvariable=self.currency_var)
        self.currency_combo.pack(fill="x", pady=(3, 9))
        self._label(form, "Price type", foreground=MUTED).pack(anchor="w")
        self.mode_combo = ttk.Combobox(form, values=PRICE_MODES, state="readonly", textvariable=self.price_mode_var)
        self.mode_combo.pack(fill="x", pady=(3, 9))
        self._label(form, "VAT % (required for gross prices)", foreground=MUTED).pack(anchor="w")
        self.vat_entry = tk.Entry(form, textvariable=self.vat_var, bg=PANEL2, fg=TEXT, insertbackground=TEXT, relief="flat", font=("Segoe UI", 10))
        self.vat_entry.pack(fill="x", ipady=7, pady=(3, 11))
        self._button(form, "Apply Offer Settings", self._apply_offer_settings, primary=True).pack(fill="x", pady=(0, 13))
        self._label(left, "AI-extracted amounts are suggestions only.\nAlways inspect the original quotation.", foreground=MUTED,
                    font=("Segoe UI", 9), justify="left", wraplength=280).pack(fill="x", padx=14, pady=(4, 14))

        self.tabs = ttk.Notebook(right)
        self.tabs.pack(fill="both", expand=True)
        self.review_tab = tk.Frame(self.tabs, bg=BG)
        self.compare_tab = tk.Frame(self.tabs, bg=BG)
        self.tabs.add(self.review_tab, text="Review & Map Items")
        self.tabs.add(self.compare_tab, text="Compare Offers & Export")
        self._build_review()
        self._build_compare()
        status = tk.Frame(self, bg=PANEL)
        status.pack(fill="x")
        self._label(status, "●  ", foreground=GREEN).pack(side="left", padx=(16, 0), pady=10)
        self._label(status, "", foreground=MUTED, font=("Segoe UI", 9), textvariable=self.status_var).pack(side="left", fill="x", padx=4)

    def _build_review(self):
        info = tk.Frame(self.review_tab, bg=BG)
        info.pack(fill="x", pady=(6, 9))
        self._label(info, "Review the extracted data before approval. Manual mapping is required for different product names.",
                    background=BG, foreground=MUTED, font=("Segoe UI", 9)).pack(side="left")
        actions = tk.Frame(self.review_tab, bg=BG)
        actions.pack(fill="x", pady=(0, 8))
        for label, command, primary in (("Add Item", self._add_item, False), ("Edit Item", self._edit_item, False),
                                         ("Delete Item", self._delete_item, False), ("Approve Selected", self._approve_selected, True),
                                         ("Approve All", self._approve_all, False)):
            self._button(actions, label, command, primary).pack(side="left", padx=(0, 6))
        ai_actions = tk.Frame(self.review_tab, bg=BG)
        ai_actions.pack(fill="x", pady=(0, 10))
        for label, command in (("Extract with Ollama", self._ai_extract), ("Auto-Map Exact Names", self._auto_map),
                                ("AI Suggest Mappings", self._ai_map)):
            self._button(ai_actions, label, command).pack(side="left", padx=(0, 6))
        self._label(ai_actions, "AI never approves items or applies suggested mappings automatically.", background=BG,
                    foreground=MUTED, font=("Segoe UI", 9)).pack(side="right", padx=7)
        body = tk.Frame(self.review_tab, bg=PANEL, highlightthickness=1, highlightbackground=EDGE)
        body.pack(fill="both", expand=True)
        cols = ("ok", "description", "qty", "unit", "price", "line", "mapped", "source")
        self.item_tree = ttk.Treeview(body, columns=cols, show="headings", selectmode="extended")
        for key, title, width in (("ok", "REVIEW", 88), ("description", "PRODUCT", 240), ("qty", "QTY", 75), ("unit", "UOM", 63),
                                  ("price", "UNIT PRICE", 98), ("line", "LINE TOTAL", 96), ("mapped", "REFERENCE MATCH", 155), ("source", "ORIGIN", 135)):
            self.item_tree.heading(key, text=title)
            self.item_tree.column(key, width=width, minwidth=max(55, int(width * 0.62)), stretch=key in ("description", "mapped", "source"))
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=self.item_tree.yview)
        xbar = ttk.Scrollbar(body, orient="horizontal", command=self.item_tree.xview)
        self.item_tree.configure(yscrollcommand=scrollbar.set, xscrollcommand=xbar.set)
        scrollbar.pack(side="right", fill="y")
        xbar.pack(side="bottom", fill="x")
        self.item_tree.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        self.item_tree.bind("<Double-1>", lambda event: self._edit_item())
        self._label(self.review_tab, "Approved ✓ = user confirmed. Issues and duplicate matches block ranking; no files are modified.",
                    background=BG, foreground=MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=9)

    def _build_compare(self):
        head = tk.Frame(self.compare_tab, bg=BG)
        head.pack(fill="x", pady=(6, 12))
        self._label(head, "Reference basket", background=BG, foreground=MUTED).pack(side="left", padx=(0, 9))
        self.reference_combo = ttk.Combobox(head, textvariable=self.reference_var, state="readonly", width=34)
        self.reference_combo.pack(side="left")
        self.reference_combo.bind("<<ComboboxSelected>>", self._change_reference)
        self._button(head, "Compare Verified Quotes", self._compare, primary=True).pack(side="left", padx=12)
        self.headline_var = tk.StringVar(value="Choose a reference quote and approve its items to start.")
        self._label(self.compare_tab, "", textvariable=self.headline_var, background=BG, foreground=AMBER,
                    font=("Segoe UI", 10), anchor="w", justify="left", wraplength=930).pack(fill="x", pady=(0, 14))
        summary_frame = tk.Frame(self.compare_tab, bg=PANEL, highlightthickness=1, highlightbackground=EDGE)
        summary_frame.pack(fill="x", pady=(0, 12))
        cols = ("supplier", "status", "total", "currency", "notes")
        self.result_tree = ttk.Treeview(summary_frame, show="headings", columns=cols, height=5)
        for key, title, width in (("supplier", "SUPPLIER", 200), ("status", "STATUS", 120), ("total", "NET MATERIAL TOTAL", 165),
                                  ("currency", "CURRENCY", 90), ("notes", "ISSUES", 330)):
            self.result_tree.heading(key, text=title)
            self.result_tree.column(key, width=width, stretch=key == "notes")
        summary_x = ttk.Scrollbar(summary_frame, orient="horizontal", command=self.result_tree.xview)
        self.result_tree.configure(xscrollcommand=summary_x.set)
        summary_x.pack(side="bottom", fill="x")
        self.result_tree.pack(fill="both", expand=True, padx=5, pady=5)
        self.result_tree.bind("<<TreeviewSelect>>", self._view_detail)
        self._label(self.compare_tab, "LINE-BY-LINE AUDIT", background=BG, foreground=PURPLE,
                    font=("Segoe UI Semibold", 10)).pack(anchor="w", pady=(0, 6))
        detail = tk.Frame(self.compare_tab, bg=PANEL, highlightbackground=EDGE, highlightthickness=1)
        detail.pack(fill="both", expand=True)
        cols = ("item", "qty", "unit", "price", "extended", "status", "note")
        self.line_tree = ttk.Treeview(detail, show="headings", columns=cols)
        for key, title, width in (("item", "REFERENCE PRODUCT", 255), ("qty", "QTY", 75), ("unit", "UOM", 70),
                                  ("price", "NET UNIT", 100), ("extended", "NET EXTENDED", 115),
                                  ("status", "STATUS", 115), ("note", "NOTES", 260)):
            self.line_tree.heading(key, text=title)
            self.line_tree.column(key, width=width, stretch=key in ("item", "note"))
        sb = ttk.Scrollbar(detail, orient="vertical", command=self.line_tree.yview)
        xbar = ttk.Scrollbar(detail, orient="horizontal", command=self.line_tree.xview)
        self.line_tree.configure(yscrollcommand=sb.set, xscrollcommand=xbar.set)
        sb.pack(side="right", fill="y")
        xbar.pack(side="bottom", fill="x")
        self.line_tree.pack(fill="both", expand=True, padx=5, pady=5)
        footer = tk.Frame(self.compare_tab, bg=BG)
        footer.pack(fill="x", pady=(11, 0))
        for text, command in (("Export Excel", lambda: self._export(".xlsx")), ("Export CSV", lambda: self._export(".csv")),
                              ("Export HTML", lambda: self._export(".html"))):
            self._button(footer, text, command).pack(side="left", padx=(0, 8))
        self._label(footer, "No currency conversion. Shipping and contract terms are excluded.", background=BG,
                    foreground=MUTED, font=("Segoe UI", 9)).pack(side="right")

    def _current_offer(self) -> Offer | None:
        selection = self.offers_list.curselection()
        if not selection or selection[0] >= len(self.offer_ids):
            return None
        return self.project.get_offer(self.offer_ids[selection[0]])

    def _selected_items(self) -> list[Item]:
        off = self._current_offer()
        if not off:
            return []
        ids = set(self.item_tree.selection())
        return [x for x in off.items if x.id in ids]

    def _refresh_offers(self, select_id: str | None = None):
        selected_id = select_id or (self._current_offer().id if self._current_offer() else None)
        self.offers_list.delete(0, "end")
        self.offer_ids = []
        for off in self.project.offers:
            self.offer_ids.append(off.id)
            star = "★ " if self.project.reference_id == off.id else ""
            self.offers_list.insert("end", f"{star}{off.supplier}  ·  {len(off.items)} lines")
        self.reference_ids = [o.id for o in self.project.offers]
        labels = [o.supplier for o in self.project.offers]
        self.reference_combo.configure(values=labels)
        if self.project.get_reference():
            self.reference_var.set(self.project.get_reference().supplier)
        else:
            self.reference_var.set("")
        if self.offer_ids:
            index = self.offer_ids.index(selected_id) if selected_id in self.offer_ids else 0
            self.offers_list.selection_set(index)
            self.offers_list.activate(index)
        self._on_offer_selected()

    def _on_offer_selected(self, event=None):
        off = self._current_offer()
        if off:
            self.supplier_var.set(off.supplier)
            self.currency_var.set(off.currency)
            self.price_mode_var.set(off.price_mode)
            self.vat_var.set(str(off.vat_rate) if off.vat_rate is not None else "")
        else:
            self.supplier_var.set("")
        self._refresh_items()

    def _refresh_items(self):
        self.item_tree.delete(*self.item_tree.get_children())
        offer = self._current_offer()
        ref = self.project.get_reference()
        if not offer:
            return
        reference_names = {x.id: x.description for x in ref.items} if ref else {}
        for item in offer.items:
            matched = "REFERENCE" if offer.id == self.project.reference_id else reference_names.get(item.ref_id, "—")
            flag = "✓ APPROVED" if item.ready() else "! REVIEW" if item.issues() else "• UNVERIFIED"
            if item.approved and item.issues():
                flag = "! FIX DATA"
            self.item_tree.insert("", "end", iid=item.id,
                                  values=(flag, item.description, _val(item.qty), item.unit, _val(item.unit_price),
                                          _val(item.line_total), matched[:65], item.source_ref[:45]))

    def _import(self):
        paths = filedialog.askopenfilenames(title="Import supplier quotations", filetypes=[("Quote PDFs and Excel", "*.pdf *.xlsx")])
        if not paths:
            return
        warnings = []
        count = 0
        for path in paths:
            try:
                offer, notes = import_offer(Path(path))
                self.project.offers.append(offer)
                warnings.extend(notes)
                count += 1
            except Exception as exc:
                warnings.append(f"{Path(path).name}: {exc}")
        if count and not self.project.reference_id:
            self.project.reference_id = self.project.offers[0].id
        self.result = None
        self._refresh_offers()
        self.status_var.set(f"Imported {count} quote(s). Approve their verified items; PDF AI extraction is optional.")
        if warnings:
            messagebox.showwarning("Import warnings", "\n".join(warnings[:14])[:2400])

    def _load_demo(self):
        if self.project.offers and not messagebox.askyesno("Replace project?", "Replace current project with the demo? Save your work first."):
            return
        directory = Path(__file__).resolve().parent.parent / "samples"
        filenames = ["Supplier_Alpha.xlsx", "Supplier_Beta.xlsx", "Supplier_Gamma.pdf"]
        demo = Project()
        notes = []
        for name in filenames:
            try:
                offer, warnings = import_offer(directory / name)
                demo.offers.append(offer)
                notes.extend(warnings)
            except Exception as exc:
                messagebox.showerror("Demo failed", f"{name}: {exc}")
                return
        demo.reference_id = demo.offers[0].id
        self.project = demo
        self.result = None
        self._refresh_offers()
        self.status_var.set("Demo loaded. Check original sample files, approve each quote, Auto-Map Exact Names, then Compare.")
        if notes:
            messagebox.showwarning("Demo notes", "\n".join(notes[:8]))

    def _remove_offer(self):
        off = self._current_offer()
        if not off:
            return
        if not messagebox.askyesno("Remove quotation", f"Remove '{off.supplier}' from this in-memory project? Source file remains untouched."):
            return
        self.project.offers = [o for o in self.project.offers if o.id != off.id]
        if self.project.reference_id == off.id:
            self.project.reference_id = self.project.offers[0].id if self.project.offers else ""
            for offer in self.project.offers:
                for item in offer.items:
                    item.ref_id = ""
        self.result = None
        self._refresh_offers()

    def _apply_offer_settings(self):
        off = self._current_offer()
        if not off:
            return
        try:
            renamed = Offer(supplier=self.supplier_var.get(), currency=self.currency_var.get(),
                            price_mode=self.price_mode_var.get(), vat_rate=self.vat_var.get().strip() or None)
        except ValueError as exc:
            messagebox.showerror("Invalid settings", str(exc))
            return
        off.supplier, off.currency, off.price_mode, off.vat_rate = renamed.supplier, renamed.currency, renamed.price_mode, renamed.vat_rate
        self.result = None
        self._refresh_offers(off.id)
        self.status_var.set("Supplier details updated. Run comparison again.")

    def _change_reference(self, event=None):
        idx = self.reference_combo.current()
        if idx < 0 or idx >= len(self.reference_ids):
            return
        new_id = self.reference_ids[idx]
        if new_id != self.project.reference_id:
            if self.project.reference_id and not messagebox.askyesno("Change basket", "Changing reference will clear ALL item mappings. Continue?"):
                self.reference_var.set(self.project.get_reference().supplier)
                return
            self.project.reference_id = new_id
            for o in self.project.offers:
                for item in o.items:
                    item.ref_id = ""
            self.result = None
            self._refresh_offers()
            self.status_var.set("Reference changed; all prior product mappings were cleared.")

    def _show_item_dialog(self, item: Item | None = None):
        offer = self._current_offer()
        if not offer:
            messagebox.showinfo("Choose a quotation", "Import a quotation first.")
            return
        ref = self.project.get_reference()
        editor = tk.Toplevel(self)
        editor.title("Edit line item" if item else "Add line item")
        editor.configure(bg=PANEL)
        editor.geometry("600x630")
        editor.transient(self)
        editor.grab_set()
        fields = {}
        specs = [("Product description", "description", item.description if item else ""),
                 ("Quantity", "qty", _val(item.qty) if item else ""),
                 ("Unit of measure", "unit", item.unit if item else "pcs"),
                 ("Unit price", "unit_price", _val(item.unit_price) if item else ""),
                 ("Line total (optional)", "line_total", _val(item.line_total) if item else "")]
        for label, key, value in specs:
            self._label(editor, label, foreground=MUTED).pack(anchor="w", padx=22, pady=(10, 3))
            var = tk.StringVar(value=value)
            if key == "unit":
                control = ttk.Combobox(editor, textvariable=var, values=UNITS, state="readonly")
            else:
                control = tk.Entry(editor, textvariable=var, bg=PANEL2, fg=TEXT, relief="flat", insertbackground=TEXT, font=("Segoe UI", 10))
            control.pack(fill="x", padx=22, ipady=3)
            fields[key] = var
        self._label(editor, "Map to reference product (only for alternate quotes)", foreground=MUTED).pack(anchor="w", padx=22, pady=(15, 3))
        choices = ["— Unmapped —"]
        ref_ids = [""]
        if ref and ref.id != offer.id:
            for base in ref.items:
                choices.append(f"{base.description} [{base.unit}]")
                ref_ids.append(base.id)
        mapped_var = tk.StringVar(value=choices[ref_ids.index(item.ref_id)] if item and item.ref_id in ref_ids else choices[0])
        mapped_box = ttk.Combobox(editor, values=choices, state="readonly", textvariable=mapped_var)
        mapped_box.pack(fill="x", padx=22)
        self._label(editor, "Source: " + (item.source_ref if item else "Manually added"), foreground=MUTED,
                    font=("Segoe UI", 9), wraplength=540, justify="left").pack(anchor="w", padx=22, pady=(16, 5))
        if item and item.evidence:
            self._label(editor, "Source evidence: " + item.evidence[:220], foreground=MUTED,
                        font=("Segoe UI", 9), wraplength=540, justify="left").pack(anchor="w", padx=22, pady=(0, 5))
        self._label(editor, "After saving, the item becomes UNVERIFIED until you approve it again.", foreground=AMBER,
                    font=("Segoe UI", 9), wraplength=540, justify="left").pack(anchor="w", padx=22, pady=(10, 10))

        def save():
            try:
                new_item = Item(description=fields["description"].get(), qty=fields["qty"].get() or None,
                                unit=fields["unit"].get(), unit_price=fields["unit_price"].get() or None,
                                line_total=fields["line_total"].get() or None,
                                source_ref=item.source_ref if item else "Manual addition (check against original)",
                                evidence=item.evidence if item else "", note=item.note if item else "Manually added; verify original.",
                                id=item.id if item else new_id(), approved=False)
                index = mapped_box.current()
                if index > 0:
                    target = ref.items[index - 1]
                    if new_item.unit != target.unit:
                        raise ValueError(f"Unit mismatch: {new_item.unit} vs {target.unit}. Convert source values after verification.")
                    new_item.ref_id = target.id
                else:
                    new_item.ref_id = ""
            except (ValueError, IndexError) as exc:
                messagebox.showerror("Invalid item", str(exc), parent=editor)
                return
            if item:
                idx = next(i for i, old in enumerate(offer.items) if old.id == item.id)
                offer.items[idx] = new_item
            else:
                offer.items.append(new_item)
            self.result = None
            self._refresh_offers(offer.id)
            editor.destroy()
            self.status_var.set("Item saved as UNVERIFIED. Confirm data against the source before approving.")
        self._button(editor, "Save & Return for Review", save, primary=True).pack(fill="x", padx=22, pady=(8, 15))

    def _add_item(self):
        self._show_item_dialog()

    def _edit_item(self):
        items = self._selected_items()
        if len(items) != 1:
            messagebox.showinfo("Edit item", "Select exactly one row.")
            return
        self._show_item_dialog(items[0])

    def _delete_item(self):
        off = self._current_offer()
        items = self._selected_items()
        if not off or not items:
            return
        if not messagebox.askyesno("Delete lines", f"Remove {len(items)} line(s) from this project? Original files will not be changed."):
            return
        remove = {x.id for x in items}
        off.items = [i for i in off.items if i.id not in remove]
        self.result = None
        self._refresh_offers(off.id)

    def _approve_selected(self):
        items = self._selected_items()
        if not items:
            messagebox.showinfo("Approve items", "Select one or more rows.")
            return
        errors = [f"{i.description}: {', '.join(i.issues())}" for i in items if i.issues()]
        if errors:
            messagebox.showwarning("Fix before approval", "\n".join(errors[:12]))
            return
        if not messagebox.askyesno("Confirm source review", f"Have you manually verified the quantities, units and prices for {len(items)} selected item(s) against the original documents?"):
            return
        for item in items:
            item.approved = True
        self.result = None
        self._refresh_items()
        self.status_var.set(f"Approved {len(items)} human-verified item(s).")

    def _approve_all(self):
        off = self._current_offer()
        if not off:
            return
        ready = [i for i in off.items if not i.issues() and not i.approved]
        problems = len([i for i in off.items if i.issues()])
        if not ready:
            messagebox.showinfo("Approve all", f"No eligible unapproved items. {problems} item(s) require correction.")
            return
        if not messagebox.askyesno("Verify all lines", f"You are confirming that you personally reviewed ALL {len(ready)} eligible rows against '{off.supplier}'.\n{problems} invalid lines will remain unapproved. Continue?"):
            return
        for item in ready:
            item.approved = True
        self.result = None
        self._refresh_items()
        self.status_var.set(f"Approved {len(ready)} items; {problems} left for correction.")

    def _auto_map(self):
        count = exact_matches(self.project)
        self.result = None
        self._refresh_items()
        self.status_var.set(f"Mapped {count} item(s) by EXACT description and matching unit; verify all mappings.")

    def _refresh_models(self):
        if self.busy:
            return
        self._start_job("models", installed_models)

    def _ai_extract(self):
        off = self._current_offer()
        if not off:
            return
        if not off.raw_text.strip():
            messagebox.showwarning("No text", "No readable document text. Scanned PDFs need OCR; not available in v0.1.")
            return
        if off.items and not messagebox.askyesno("Replace extracted rows", "AI extraction will REPLACE the current items for this supplier, including approvals and mappings. Continue?"):
            return
        self._start_job("extract", lambda: extract_items(off, self.model_var.get().strip(), progress=lambda m: self._jobs.put(("progress", m))), off.id)

    def _ai_map(self):
        off = self._current_offer()
        ref = self.project.get_reference()
        if not off or not ref or off.id == ref.id:
            messagebox.showinfo("Choose alternate quote", "Select an alternate supplier after choosing a reference basket.")
            return
        self._start_job("map", lambda: suggest_mappings(off, ref, self.model_var.get().strip()), off.id)

    def _start_job(self, task, func, off_id=None):
        if self.busy:
            return
        self.busy = True
        self.status_var.set(f"Ollama processing: {task}. Please keep the application open...")
        def worker():
            try:
                result = func()
                self._jobs.put((task, off_id, result))
            except Exception as exc:
                self._jobs.put(("error", None, str(exc)))
        Thread(target=worker, daemon=True).start()

    def _poll(self):
        try:
            while True:
                event = self._jobs.get_nowait()
                kind = event[0]
                if kind == "progress":
                    self.status_var.set(event[1])
                elif kind == "error":
                    self.busy = False
                    self.status_var.set("Ollama task failed: " + event[2])
                    messagebox.showerror("Ollama error", event[2])
                elif kind == "models":
                    self.busy = False
                    names = event[2]
                    self.models_combo.configure(values=names)
                    if names and self.model_var.get() not in names:
                        self.model_var.set(names[0])
                    self.status_var.set(f"Ollama online; {len(names)} installed model(s) available.")
                elif kind == "extract":
                    self.busy = False
                    off = self.project.get_offer(event[1])
                    if off:
                        items, warnings = event[2]
                        off.items = items
                        self.result = None
                        self._refresh_offers(off.id)
                        self.status_var.set(f"AI extracted {len(items)} UNVERIFIED rows; manually inspect and approve them.")
                        if warnings:
                            messagebox.showwarning("Extraction warnings", "\n".join(warnings[:15])[:2500])
                elif kind == "map":
                    self.busy = False
                    off = self.project.get_offer(event[1])
                    if off:
                        self._confirm_ai_mappings(off, event[2])
        except queue.Empty:
            pass
        self.after(130, self._poll)

    def _confirm_ai_mappings(self, off: Offer, pairs: list[tuple[str, str, str]]):
        ref = self.project.get_reference()
        if not pairs or not ref:
            messagebox.showinfo("AI mappings", "No candidate product matches were suggested.")
            return
        lookup_a = {x.id: x for x in off.items}
        lookup_b = {x.id: x for x in ref.items}
        dialog = tk.Toplevel(self)
        dialog.title("AI Mapping Suggestions — Human Approval Required")
        dialog.geometry("880x480")
        dialog.configure(bg=PANEL)
        dialog.transient(self)
        dialog.grab_set()
        self._label(dialog, "Only apply mappings you have checked for equivalent product specifications.", foreground=AMBER,
                    font=("Segoe UI Semibold", 10)).pack(fill="x", padx=18, pady=15)
        listing = tk.Listbox(dialog, selectmode="extended", bg=PANEL2, fg=TEXT, selectbackground="#574487", relief="flat", font=("Segoe UI", 10))
        listing.pack(fill="both", expand=True, padx=18, pady=(0, 12))
        visible = []
        for a, b, reason in pairs:
            if a in lookup_a and b in lookup_b:
                listing.insert("end", f"{lookup_a[a].description[:42]}  ⇒  {lookup_b[b].description[:42]}    ({reason[:65]})")
                visible.append((a, b))

        def apply():
            idxs = listing.curselection()
            if not idxs:
                messagebox.showinfo("Select suggestions", "Select only the pairs you have verified.", parent=dialog)
                return
            if not messagebox.askyesno("Confirm equivalence", f"Apply {len(idxs)} mappings after verifying unit and specification compatibility?", parent=dialog):
                return
            applied = 0
            errors = []
            for index in idxs:
                try:
                    a, b = visible[index]
                    map_item(self.project, off.id, a, b)
                    applied += 1
                except ValueError as exc:
                    errors.append(str(exc))
            dialog.destroy()
            self.result = None
            self._refresh_items()
            self.status_var.set(f"Manually confirmed and applied {applied} AI mapping suggestions.")
            if errors:
                messagebox.showwarning("Skipped matches", "\n".join(errors[:8]))
        self._button(dialog, "Apply Selected, Confirmed Mappings", apply, primary=True).pack(fill="x", padx=18, pady=(0, 16))

    def _compare(self):
        self.result = compare_project(self.project)
        comp = self.result
        self.headline_var.set(comp.headline)
        self.result_tree.delete(*self.result_tree.get_children())
        self.line_tree.delete(*self.line_tree.get_children())
        for off in comp.results:
            total = f"{off.total_net:,.2f}" if off.total_net is not None else "NOT RANKED"
            prefix = "★ " if off.offer_id in comp.winner_ids else ""
            self.result_tree.insert("", "end", iid=off.offer_id,
                                    values=(prefix + off.supplier, off.status, total, off.currency, "; ".join(off.messages)))
        if comp.results:
            self.result_tree.selection_set(comp.results[0].offer_id)
            self._view_detail()
        self.status_var.set("Comparison refreshed. Never treat incomplete or mixed-currency offers as a winner.")
        if not comp.results:
            messagebox.showwarning("Comparison blocked", comp.headline)

    def _view_detail(self, event=None):
        self.line_tree.delete(*self.line_tree.get_children())
        if not self.result:
            return
        choices = self.result_tree.selection()
        if not choices:
            return
        res = next((r for r in self.result.results if r.offer_id == choices[0]), None)
        if not res:
            return
        for idx, line in enumerate(res.lines):
            self.line_tree.insert("", "end", iid=str(idx),
                                  values=(line.description, _val(line.qty), line.unit, _val(line.offered_price),
                                          _val(line.extended_net), line.status, line.note))

    def _export(self, suffix: str):
        if not self.result or not self.result.results:
            messagebox.showinfo("Run comparison first", "Choose a reference offer, approve items, then Compare Verified Quotes.")
            return
        file_path = filedialog.asksaveasfilename(defaultextension=suffix,
                     filetypes=[({".csv": "CSV", ".xlsx": "Excel", ".html": "HTML"}[suffix] + " Report", "*" + suffix)],
                     initialfile="NEXUS_Quote_Comparison" + suffix)
        if not file_path:
            return
        destination = Path(file_path)
        if destination.exists() and not messagebox.askyesno("Replace file?", "This destination exists. Replace it?"):
            return
        try:
            if suffix == ".csv":
                if destination.exists():
                    destination.unlink()  # Only after explicit confirmation above
                export_csv(self.result, destination)
            elif suffix == ".html":
                export_html(self.result, destination)
            elif suffix == ".xlsx":
                export_xlsx(self.result, destination)
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc))
            return
        self.status_var.set("Report saved: " + str(destination))
        if suffix == ".html" and messagebox.askyesno("Open report?", "Open the HTML report in your browser?"):
            webbrowser.open(destination.resolve().as_uri())

    def _save_project(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".nqc.json", filetypes=[("NEXUS QuoteCheck Project", "*.nqc.json")], initialfile="MyQuotes.nqc.json")
        if not file_path:
            return
        try:
            self.project.save(Path(file_path))
        except Exception as exc:
            messagebox.showerror("Save error", str(exc))
            return
        self.status_var.set(f"Project saved: {file_path}. Original PDF and XLSX files are not copied.")

    def _open_project(self):
        file_path = filedialog.askopenfilename(filetypes=[("NEXUS QuoteCheck Project", "*.nqc.json")])
        if not file_path:
            return
        if self.project.offers and not messagebox.askyesno("Replace current project?", "Current in-memory project will be replaced. Save it first if needed."):
            return
        try:
            self.project = Project.load(Path(file_path))
        except Exception as exc:
            messagebox.showerror("Project load error", str(exc))
            return
        self.result = None
        self._refresh_offers()
        self.status_var.set("Project loaded. Source paths are recorded, but originals were not modified.")


def _val(value):
    return "" if value is None else str(value)


def main():
    QuoteCheckApp().mainloop()
