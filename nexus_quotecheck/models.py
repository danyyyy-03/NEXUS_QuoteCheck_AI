"""Validated domain models; all price arithmetic uses Decimal, never LLM math."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import uuid4
import json
import re

CURRENCIES = ("RON", "EUR", "USD")
PRICE_MODES = ("Net (excl. VAT)", "Gross (incl. VAT)")
UNITS = ("pcs", "m", "m2", "m3", "kg", "g", "l", "set", "roll", "box", "pack", "other")
UNIT_ALIASES = {
    "piece": "pcs", "pieces": "pcs", "buc": "pcs", "buc.": "pcs", "unit": "pcs", "units": "pcs", "each": "pcs", "ea": "pcs", "pc": "pcs", "pcs": "pcs",
    "meter": "m", "metre": "m", "meters": "m", "metres": "m", "ml": "m", "m": "m",
    "m²": "m2", "sqm": "m2", "m2": "m2", "m³": "m3", "m3": "m3",
    "kg": "kg", "kilogram": "kg", "g": "g", "gram": "g", "liter": "l", "litre": "l", "l": "l",
    "sets": "set", "set": "set", "role": "roll", "roll": "roll", "rolls": "roll",
    "boxes": "box", "box": "box", "pachet": "pack", "pack": "pack", "packs": "pack", "other": "other",
}


def new_id() -> str:
    return uuid4().hex[:12]


def parse_decimal(value: object, *, allow_none: bool = True) -> Decimal | None:
    """Conservative number parsing: ambiguous separators are rejected, not guessed."""
    if value is None or str(value).strip() == "":
        if allow_none:
            return None
        raise ValueError("Value is required")
    if isinstance(value, bool):
        raise ValueError("Boolean is not a number")
    if isinstance(value, (float, int, Decimal)):
        s = str(value)
    else:
        s = str(value).strip().replace("\u00a0", " ").replace(" ", "")
        s = re.sub(r"(?:RON|EUR|USD|lei|€|\$)$", "", s, flags=re.IGNORECASE).strip()
        if not s:
            raise ValueError("No number")
        if "," in s and "." in s:
            s = s.replace(",", "") if s.rfind(".") > s.rfind(",") else s.replace(".", "").replace(",", ".")
        elif "," in s:
            if s.count(",") > 1:
                raise ValueError(f"Ambiguous number: {value}")
            s = s.replace(",", ".")
        # Do not assume 1.000 means one thousand: it may mean one with 3 decimals.
    try:
        d = Decimal(s)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid number: {value}") from exc
    if not d.is_finite() or abs(d) > Decimal("1000000000000"):
        raise ValueError("Number must be finite and within permitted range")
    return d


def positive_number(value: object, name: str) -> Decimal:
    d = parse_decimal(value, allow_none=False)
    if d <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return d


def normalize_unit(value: object) -> str:
    raw = str(value or "").casefold().strip()
    return UNIT_ALIASES.get(raw, raw or "other")


@dataclass
class Item:
    description: str
    qty: Decimal | None
    unit: str
    unit_price: Decimal | None
    line_total: Decimal | None = None
    id: str = field(default_factory=new_id)
    ref_id: str = ""
    approved: bool = False
    source_ref: str = ""
    evidence: str = ""
    note: str = ""

    def __post_init__(self):
        self.description = str(self.description).strip()[:400]
        self.unit = normalize_unit(self.unit)
        self.qty = parse_decimal(self.qty)
        self.unit_price = parse_decimal(self.unit_price)
        self.line_total = parse_decimal(self.line_total)
        self.note = str(self.note or "")[:500]
        if not self.description:
            raise ValueError("Description is required")
        if self.qty is not None and self.qty <= 0:
            raise ValueError("Quantity must be greater than zero")
        if self.unit_price is not None and self.unit_price < 0:
            raise ValueError("Unit price cannot be negative")
        if self.line_total is not None and self.line_total < 0:
            raise ValueError("Line total cannot be negative")

    def issues(self) -> list[str]:
        out = []
        if self.qty is None:
            out.append("missing quantity")
        if self.unit_price is None:
            out.append("missing unit price")
        if self.unit in ("", "other"):
            out.append("unknown unit")
        if self.line_total is not None and self.qty is not None and self.unit_price is not None:
            if abs(self.line_total - self.qty * self.unit_price) > Decimal("0.05"):
                out.append("line total differs from quantity × unit price")
        return out

    def ready(self) -> bool:
        return self.approved and not self.issues()

    def to_dict(self) -> dict:
        data = asdict(self)
        for key in ("qty", "unit_price", "line_total"):
            data[key] = str(data[key]) if data[key] is not None else None
        return data

    @classmethod
    def from_dict(cls, raw: dict) -> "Item":
        permitted = {k: raw.get(k) for k in ("description", "qty", "unit", "unit_price", "line_total", "id", "ref_id", "approved", "source_ref", "evidence", "note") if k in raw}
        return cls(**permitted)


@dataclass
class Offer:
    supplier: str
    currency: str = "RON"
    price_mode: str = "Net (excl. VAT)"
    vat_rate: Decimal | None = None  # percentage, used for gross -> net
    items: list[Item] = field(default_factory=list)
    id: str = field(default_factory=new_id)
    source_path: str = ""
    raw_text: str = ""

    def __post_init__(self):
        self.supplier = str(self.supplier).strip()[:120]
        if not self.supplier:
            raise ValueError("Supplier name is required")
        self.currency = str(self.currency).upper()
        if self.currency not in CURRENCIES:
            raise ValueError("Unsupported currency")
        if self.price_mode not in PRICE_MODES:
            raise ValueError("Unsupported price mode")
        self.vat_rate = parse_decimal(self.vat_rate)
        if self.vat_rate is not None and not (Decimal("0") <= self.vat_rate <= Decimal("100")):
            raise ValueError("VAT percentage must be between 0 and 100")

    def to_dict(self) -> dict:
        return {
            "id": self.id, "supplier": self.supplier, "currency": self.currency,
            "price_mode": self.price_mode, "vat_rate": str(self.vat_rate) if self.vat_rate is not None else None,
            "source_path": self.source_path, "raw_text": self.raw_text[:50000],
            "items": [i.to_dict() for i in self.items],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Offer":
        return cls(
            supplier=data["supplier"], currency=data.get("currency", "RON"),
            price_mode=data.get("price_mode", PRICE_MODES[0]), vat_rate=data.get("vat_rate"),
            items=[Item.from_dict(x) for x in data.get("items", [])],
            id=data.get("id", new_id()), source_path=data.get("source_path", ""),
            raw_text=data.get("raw_text", ""),
        )


@dataclass
class Project:
    offers: list[Offer] = field(default_factory=list)
    reference_id: str = ""

    def to_dict(self) -> dict:
        return {"format": "nexus-quotecheck-project", "version": 1, "reference_id": self.reference_id, "offers": [o.to_dict() for o in self.offers]}

    @classmethod
    def from_dict(cls, data: dict) -> "Project":
        if data.get("format") != "nexus-quotecheck-project" or data.get("version") != 1:
            raise ValueError("Unsupported project file")
        offers = [Offer.from_dict(x) for x in data.get("offers", [])]
        return cls(offers=offers, reference_id=data.get("reference_id", ""))

    def get_reference(self) -> Offer | None:
        return next((o for o in self.offers if o.id == self.reference_id), None)

    def get_offer(self, ident: str) -> Offer | None:
        return next((o for o in self.offers if o.id == ident), None)

    def save(self, path: Path) -> None:
        import os
        import tempfile
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False) as handle:
            temp_path = Path(handle.name)
            json.dump(self.to_dict(), handle, indent=2, ensure_ascii=False)
        os.replace(temp_path, path)

    @classmethod
    def load(cls, path: Path) -> "Project":
        path = Path(path)
        if path.stat().st_size > 5_000_000:
            raise ValueError("Project too large")
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
