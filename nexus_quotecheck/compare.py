"""Audit-friendly supplier comparisons without LLM calculations or made-up rankings."""
from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from .models import Project, Offer, Item, PRICE_MODES

CENT = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def net_unit_price(item: Item, offer: Offer) -> Decimal:
    if item.unit_price is None:
        raise ValueError("Missing price")
    if offer.price_mode == PRICE_MODES[0]:
        return item.unit_price
    if offer.vat_rate is None:
        raise ValueError("Gross price needs confirmed VAT percentage")
    return item.unit_price / (Decimal(1) + offer.vat_rate / Decimal(100))


@dataclass
class LineResult:
    base_id: str
    description: str
    qty: Decimal
    unit: str
    offered_price: Decimal | None
    extended_net: Decimal | None
    status: str
    note: str = ""


@dataclass
class OfferResult:
    offer_id: str
    supplier: str
    currency: str
    lines: list[LineResult] = field(default_factory=list)
    total_net: Decimal | None = None
    status: str = "BLOCKED"
    messages: list[str] = field(default_factory=list)


@dataclass
class Comparison:
    reference_supplier: str
    currency: str
    items_count: int
    results: list[OfferResult]
    winner_ids: list[str]
    headline: str


def compare_project(project: Project) -> Comparison:
    ref = project.get_reference()
    if not ref:
        return Comparison("", "", 0, [], [], "Choose a reference offer first")
    if not ref.items:
        return Comparison(ref.supplier, ref.currency, 0, [], [], "Reference offer has no items")
    # An incomplete reference basket must not silently shrink: fail the entire comparison.
    invalid_refs = [i for i in ref.items if not i.ready()]
    if invalid_refs:
        return Comparison(ref.supplier, ref.currency, len(ref.items), [], [],
                          f"Approve and correct ALL {len(ref.items)} reference items first ({len(invalid_refs)} not ready)")
    results = []
    for off in project.offers:
        result = OfferResult(off.id, off.supplier, off.currency)
        if off.currency != ref.currency:
            result.messages.append(f"Currency {off.currency} differs from reference {ref.currency}; no exchange rate assumed")
        if off.price_mode == PRICE_MODES[1] and off.vat_rate is None:
            result.messages.append("Gross prices require confirmed VAT percentage")
        possible: list[Decimal] = []
        for base in ref.items:
            candidates = [base] if off.id == ref.id else [i for i in off.items if i.ref_id == base.id]
            if len(candidates) != 1:
                reason = "Missing matching product" if not candidates else "Multiple matches: resolve duplicates"
                result.lines.append(LineResult(base.id, base.description, base.qty, base.unit, None, None, "MISSING" if not candidates else "DUPLICATE", reason))
                continue
            item = candidates[0]
            if item.unit != base.unit:
                result.lines.append(LineResult(base.id, base.description, base.qty, base.unit, None, None, "UNIT MISMATCH", f"{item.unit} vs {base.unit}"))
                continue
            if not item.ready():
                result.lines.append(LineResult(base.id, base.description, base.qty, base.unit, item.unit_price, None, "REVIEW", ", ".join(item.issues()) if item.issues() else "Not approved"))
                continue
            try:
                price = net_unit_price(item, off)
                extended = money(base.qty * price)
            except ValueError as exc:
                result.lines.append(LineResult(base.id, base.description, base.qty, base.unit, item.unit_price, None, "VAT REVIEW", str(exc)))
                continue
            result.lines.append(LineResult(base.id, base.description, base.qty, base.unit, money(price), extended, "OK"))
            possible.append(extended)
        if len(possible) == len(ref.items) and not result.messages:
            result.status = "COMPLETE"
            result.total_net = sum(possible, Decimal(0))
        else:
            result.status = "INCOMPLETE"
            if any(line.status != "OK" for line in result.lines):
                result.messages.append("Missing, duplicated, unapproved or invalid items — not ranked")
        results.append(result)
    qualified = [r for r in results if r.total_net is not None]
    if not qualified:
        return Comparison(ref.supplier, ref.currency, len(ref.items), results, [], "No complete comparable quote. Resolve review flags.")
    best = min(r.total_net for r in qualified)
    winners = [r.offer_id for r in qualified if r.total_net == best]
    explanation = f"Lowest verified material total among {len(qualified)} complete offer(s); excludes shipping/discounts and contractual differences."
    if len(qualified) < len(results):
        explanation += " Some offers are incomplete or incomparable and are NOT included in this ranking."
    return Comparison(ref.supplier, ref.currency, len(ref.items), results, winners, explanation)
