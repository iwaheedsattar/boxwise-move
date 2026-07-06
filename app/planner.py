from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta
from math import log
import re
from typing import Iterable


ROOM_KEYWORDS = {
    "kitchen": "Kitchen",
    "pantry": "Kitchen",
    "garage": "Garage",
    "bath": "Bathroom",
    "bed": "Bedroom",
    "closet": "Bedroom",
    "office": "Office",
    "desk": "Office",
    "living": "Living Room",
    "dining": "Dining Room",
    "laundry": "Laundry",
    "kids": "Kids Room",
    "nursery": "Kids Room",
    "outdoor": "Outdoor",
    "patio": "Outdoor",
}

CATEGORY_KEYWORDS = {
    "fragile": ["glass", "frame", "mirror", "ceramic", "plate", "mug", "lamp", "vase"],
    "essentials": ["toothbrush", "charger", "medicine", "medication", "coffee", "pet food", "diaper", "keys"],
    "documents": ["passport", "lease", "title", "birth certificate", "tax", "records", "paperwork"],
    "heavy": ["books", "dumbbell", "tool", "cast iron", "files", "weights"],
    "donate": ["extra", "unused", "old", "outgrown", "duplicate", "donate"],
    "sell": ["bike", "desk", "dresser", "chair", "table", "monitor", "sofa"],
}

STAGE_LABELS = [
    ("pack_now", "Pack now"),
    ("pack_next", "Pack next"),
    ("last_week", "Last week"),
    ("last_day", "Last day"),
]


@dataclass
class MoveItem:
    name: str
    room: str
    quantity: int
    frequency: str
    sentiment: str
    notes: str


@dataclass
class PlannedItem:
    name: str
    room: str
    quantity: int
    category: str
    stage: str
    action: str
    box_label: str
    risk_score: int
    rationale: str


@dataclass
class MovePlan:
    move_date: str
    days_until_move: int
    stage_summary: dict[str, int]
    room_summary: dict[str, int]
    items: list[PlannedItem]
    timeline: list[dict[str, str]]
    first_night_kit: list[str]
    donation_or_sale: list[str]
    supply_list: list[dict[str, str | int]]
    label_sheet: list[str]
    coach_notes: list[str]


def parse_items(raw: str) -> list[MoveItem]:
    rows: list[MoveItem] = []
    for line in raw.splitlines():
        clean = line.strip()
        if not clean or clean.lower().startswith(("item,", "name,")):
            continue
        parts = [part.strip() for part in re.split(r",|\t", clean)]
        while len(parts) < 5:
            parts.append("")
        name, room, quantity, frequency, sentiment, *notes = parts
        inferred_room = room or infer_room(name)
        rows.append(
            MoveItem(
                name=name,
                room=inferred_room,
                quantity=_safe_int(quantity, 1),
                frequency=(frequency or "monthly").lower(),
                sentiment=(sentiment or "neutral").lower(),
                notes=" ".join(notes).strip(),
            )
        )
    return rows


def build_plan(raw_items: str, move_date: str | None = None, home_size: str = "2 bedroom") -> MovePlan:
    items = parse_items(raw_items)
    target = _parse_date(move_date)
    today = date.today()
    days_until = max(0, (target - today).days)
    planned = [_plan_item(item, idx + 1) for idx, item in enumerate(items)]
    planned.sort(key=lambda item: (_stage_rank(item.stage), -item.risk_score, item.room, item.name))

    stage_summary = {label: 0 for _, label in STAGE_LABELS}
    room_summary: dict[str, int] = {}
    for item in planned:
        stage_summary[item.stage] = stage_summary.get(item.stage, 0) + item.quantity
        room_summary[item.room] = room_summary.get(item.room, 0) + item.quantity

    return MovePlan(
        move_date=target.isoformat(),
        days_until_move=days_until,
        stage_summary=stage_summary,
        room_summary=dict(sorted(room_summary.items())),
        items=planned,
        timeline=_timeline(target, days_until, planned),
        first_night_kit=_first_night_kit(planned),
        donation_or_sale=[item.name for item in planned if item.action in {"Donate", "Sell"}],
        supply_list=_supplies(planned, home_size),
        label_sheet=[item.box_label for item in planned],
        coach_notes=_coach_notes(planned, days_until),
    )


def export_markdown(plan: MovePlan) -> str:
    lines = [
        "# Boxwise Move Plan",
        "",
        f"Move date: {plan.move_date}",
        f"Days until move: {plan.days_until_move}",
        "",
        "## Timeline",
    ]
    for step in plan.timeline:
        lines.append(f"- **{step['when']}**: {step['task']}")
    lines.extend(["", "## Packing Labels"])
    for label in plan.label_sheet:
        lines.append(f"- {label}")
    lines.extend(["", "## First-Night Kit"])
    for name in plan.first_night_kit:
        lines.append(f"- {name}")
    lines.extend(["", "## Donate Or Sell"])
    for name in plan.donation_or_sale:
        lines.append(f"- {name}")
    return "\n".join(lines) + "\n"


def infer_room(text: str) -> str:
    lowered = text.lower()
    for keyword, room in ROOM_KEYWORDS.items():
        if keyword in lowered:
            return room
    return "General"


def _plan_item(item: MoveItem, index: int) -> PlannedItem:
    text = " ".join([item.name, item.room, item.frequency, item.sentiment, item.notes]).lower()
    category_scores = _category_scores(text)
    category = max(category_scores, key=category_scores.get)
    risk = _risk_score(item, category)
    action = _action(item, category)
    stage = _stage(item, category, action)
    label_code = f"{item.room[:3].upper()}-{index:02d}"
    label = f"{label_code} | {item.room} | {stage} | {item.name}"
    rationale = _rationale(item, category, action, stage)
    return PlannedItem(
        name=item.name,
        room=item.room,
        quantity=item.quantity,
        category=category.title(),
        stage=stage,
        action=action,
        box_label=label,
        risk_score=risk,
        rationale=rationale,
    )


def _category_scores(text: str) -> dict[str, float]:
    scores = {name: log(1.0 / len(CATEGORY_KEYWORDS)) for name in CATEGORY_KEYWORDS}
    for name, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                scores[name] += 1.6
    if not any(score > -1.0 for score in scores.values()):
        scores["heavy"] -= 0.4
    return scores


def _risk_score(item: MoveItem, category: str) -> int:
    score = 20 + min(item.quantity * 4, 20)
    if category in {"fragile", "documents", "essentials"}:
        score += 30
    if category == "heavy":
        score += 18
    if item.frequency in {"daily", "weekly"}:
        score += 12
    if item.sentiment in {"high", "irreplaceable", "sentimental"}:
        score += 18
    return min(score, 100)


def _action(item: MoveItem, category: str) -> str:
    if category == "donate":
        return "Donate"
    if category == "sell" and item.sentiment not in {"high", "sentimental", "irreplaceable"}:
        return "Sell"
    if category == "fragile":
        return "Wrap"
    if category == "documents":
        return "Carry"
    if category == "essentials":
        return "Keep out"
    return "Pack"


def _stage(item: MoveItem, category: str, action: str) -> str:
    if action in {"Donate", "Sell"}:
        return "Pack now"
    if category in {"essentials", "documents"} or item.frequency == "daily":
        return "Last day"
    if item.frequency == "weekly":
        return "Last week"
    return "Pack now" if item.frequency in {"rarely", "seasonal", "never"} else "Pack next"


def _timeline(target: date, days_until: int, items: Iterable[PlannedItem]) -> list[dict[str, str]]:
    staged = {item.stage for item in items}
    steps = [
        {"when": _window(target, 21), "task": "Clear donations, list sale items, and pack seasonal storage."},
        {"when": _window(target, 14), "task": "Pack low-use rooms, books, decor, and duplicate kitchen gear."},
        {"when": _window(target, 7), "task": "Pack weekly-use items and confirm utilities, address changes, and supplies."},
        {"when": _window(target, 1), "task": "Build the first-night kit, carry documents, and leave chargers out."},
    ]
    if days_until < 10:
        steps.insert(0, {"when": "Today", "task": "Use the compressed plan: donations, fragile wrapping, and labels first."})
    if "Last day" not in staged:
        steps.append({"when": "Move morning", "task": "Sweep each room by label code before the truck leaves."})
    return steps


def _first_night_kit(items: Iterable[PlannedItem]) -> list[str]:
    kit = [item.name for item in items if item.action in {"Keep out", "Carry"} or item.stage == "Last day"]
    defaults = ["toiletries", "phone chargers", "basic tools", "coffee or tea", "two changes of clothes"]
    for item in defaults:
        if item not in kit:
            kit.append(item)
    return kit[:10]


def _supplies(items: Iterable[PlannedItem], home_size: str) -> list[dict[str, str | int]]:
    planned = list(items)
    count = sum(max(1, item.quantity) for item in planned)
    bedrooms = _safe_int(re.sub(r"\D", "", home_size), 2)
    fragile_count = sum(1 for item in planned if item.category == "Fragile")
    return [
        {"name": "Small boxes", "quantity": max(6, count // 3 + bedrooms * 2), "why": "Books, tools, pantry, and heavy items"},
        {"name": "Medium boxes", "quantity": max(8, count // 2 + bedrooms * 3), "why": "General packing by room"},
        {"name": "Packing paper", "quantity": max(1, fragile_count + 1), "why": "Glass, frames, lamps, and kitchen breakables"},
        {"name": "Label tape", "quantity": max(2, bedrooms + 1), "why": "Room codes and last-day labels"},
    ]


def _coach_notes(items: list[PlannedItem], days_until: int) -> list[str]:
    notes = []
    donate_count = sum(1 for item in items if item.action in {"Donate", "Sell"})
    carry_count = sum(1 for item in items if item.action == "Carry")
    if donate_count:
        notes.append(f"Handle {donate_count} donation or sale item(s) before buying more boxes.")
    if carry_count:
        notes.append(f"Keep {carry_count} document or high-trust item(s) out of the moving truck.")
    if days_until <= 7:
        notes.append("Use room sweeps instead of perfect sorting; speed matters more this close to move day.")
    notes.append("Put label codes on two sides of every box so they are visible when stacked.")
    return notes


def _rationale(item: MoveItem, category: str, action: str, stage: str) -> str:
    return f"{category.title()} signal with {item.frequency or 'normal'} use; recommended action is {action.lower()} and stage is {stage.lower()}."


def _window(target: date, days_before: int) -> str:
    day = target - timedelta(days=days_before)
    return f"{day.strftime('%b')} {day.day}"


def _parse_date(value: str | None) -> date:
    if not value:
        return date.today() + timedelta(days=28)
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return date.today() + timedelta(days=28)


def _stage_rank(stage: str) -> int:
    order = {"Pack now": 0, "Pack next": 1, "Last week": 2, "Last day": 3}
    return order.get(stage, 4)


def _safe_int(value: str | int, default: int) -> int:
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return default


def plan_to_dict(plan: MovePlan) -> dict:
    return asdict(plan)
