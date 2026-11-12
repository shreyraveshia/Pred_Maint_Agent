"""Renders past_work_orders.json into markdown documents for RAG indexing.
The JSON stays the single source of truth (Phase 4 also seeds the maintenance DB from it)."""
import json
from pathlib import Path

CORPUS = Path(__file__).resolve().parent.parent / "data" / "corpus"


def render_wo(w: dict) -> str:
    parts = ", ".join(f"{p['part_id']} x{p['qty']}" for p in w["parts_used"]) or "none"
    return (f"# {w['wo_id']} Past work order: {w['fault']}\nAsset: {w['asset_id']} | Date: {w['date']} | Status: {w['status']}\n\n"
            f"## Symptoms\n{w['symptoms']}\n\n## Root cause\n{w['root_cause']}\n\n"
            f"## Action taken\n{w['action_taken']} Parts used: {parts}. Downtime: {w['downtime_hours']} hours.\n\n"
            f"## Outcome\n{w['outcome']}\n")


def main():
    for w in json.loads((CORPUS / "past_work_orders.json").read_text()):
        (CORPUS / f"{w['wo_id']}.md").write_text(render_wo(w))
    print("rendered", len(list(CORPUS.glob("WO-*.md"))), "work-order docs")


if __name__ == "__main__":
    main()
