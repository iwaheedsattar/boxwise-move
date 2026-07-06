from app.planner import build_plan, export_markdown, infer_room, parse_items


SAMPLE = """item,room,quantity,frequency,sentiment,notes
passport packet,office,1,daily,high,carry it
glass bowls,kitchen,3,monthly,medium,fragile
old desk,office,1,rarely,low,sell
medicine bin,bathroom,1,daily,high,keep out
"""


def test_parse_items_skips_header_and_preserves_fields():
    items = parse_items(SAMPLE)
    assert len(items) == 4
    assert items[0].name == "passport packet"
    assert items[1].quantity == 3


def test_build_plan_creates_actionable_sections():
    plan = build_plan(SAMPLE, "2026-08-01", "2 bedroom")
    names = [item.name for item in plan.items]
    assert "medicine bin" in plan.first_night_kit
    assert "old desk" in plan.donation_or_sale
    assert len(plan.timeline) >= 4
    assert any("passport packet" in label for label in plan.label_sheet)
    assert names[0] == "old desk"


def test_export_markdown_includes_labels_and_kit():
    plan = build_plan(SAMPLE, "2026-08-01")
    markdown = export_markdown(plan)
    assert "## Packing Labels" in markdown
    assert "medicine bin" in markdown


def test_room_inference_from_item_name():
    assert infer_room("bedroom closet bins") == "Bedroom"

