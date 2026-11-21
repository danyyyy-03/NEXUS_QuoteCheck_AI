"""Conservative exact matching; AI suggestions are never applied automatically."""
from __future__ import annotations
import re
import unicodedata
from .models import Project, Item


def normalize_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value).casefold()
    cleaned = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^\w]+", " ", cleaned, flags=re.UNICODE)).strip()


def exact_matches(project: Project) -> int:
    """Only link when one unique description+unit match exists in the reference."""
    reference = project.get_reference()
    if reference is None:
        return 0
    grouped: dict[tuple[str, str], list[str]] = {}
    for item in reference.items:
        grouped.setdefault((normalize_name(item.description), item.unit), []).append(item.id)
    n = 0
    for offer in project.offers:
        if offer.id == reference.id:
            continue
        for item in offer.items:
            if item.ref_id:
                continue
            candidates = grouped.get((normalize_name(item.description), item.unit), [])
            if len(candidates) == 1:
                item.ref_id = candidates[0]
                n += 1
    return n


def map_item(project: Project, offer_id: str, item_id: str, ref_id: str) -> None:
    ref = project.get_reference()
    off = project.get_offer(offer_id)
    if not ref or not off or off.id == ref.id:
        raise ValueError("Select a non-reference offer")
    item = next((i for i in off.items if i.id == item_id), None)
    target = next((i for i in ref.items if i.id == ref_id), None)
    if not item or not target:
        raise ValueError("Unknown item")
    if item.unit != target.unit:
        raise ValueError(f"Units differ: {item.unit} vs. {target.unit}; convert manually after verifying packaging")
    item.ref_id = target.id
