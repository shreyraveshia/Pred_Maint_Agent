import json, re
from pathlib import Path
from data_gen.render_corpus import render_wo

CORPUS = Path(__file__).resolve().parent.parent / "data" / "corpus"
DOCS = sorted(CORPUS.glob("*.md"))


def test_between_8_and_10_documents():
    assert 8 <= len(DOCS) <= 10


def test_every_doc_has_unique_id_and_sections():
    ids = []
    for p in DOCS:
        text = p.read_text()
        m = re.match(r"# ((?:MAN|WO)-[A-Z0-9-]+)", text)
        assert m, p.name
        assert m.group(1) == p.stem
        assert "\n## " in text, f"{p.name} has no sections"
        ids.append(m.group(1))
    assert len(ids) == len(set(ids))


def test_rendered_work_orders_match_json():
    for w in json.loads((CORPUS / "past_work_orders.json").read_text()):
        assert (CORPUS / f"{w['wo_id']}.md").read_text() == render_wo(w)


def test_no_manual_covers_current_anomaly():
    """M-204 (current creep at constant load) must have no direct coverage, so the system must say 'no evidence'."""
    banned = ["winding", "current anomaly", "constant load"]
    for p in DOCS:
        low = p.read_text().lower()
        assert not any(b in low for b in banned), p.name


def test_every_part_in_workorders_is_in_catalogue():
    cat = (CORPUS / "MAN-SPARES-001.md").read_text()
    for w in json.loads((CORPUS / "past_work_orders.json").read_text()):
        for p in w["parts_used"]:
            assert p["part_id"] in cat
