# Sentinel - Predictive Maintenance Agent (Parkar Use Case 2)
Math detects. AI explains with citations. Humans approve.

## Setup
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # fill in Azure values
pytest                  # contracts + permissions tests should pass
python scripts/azure_smoke_test.py

## Layout
contracts/  shared schemas + permission loader (change only with team agreement)
config/     permissions.yaml (agent allow-list and never-do list)
docs/       scorecard, acceptance targets, fault catalogue, MCP tool contract

## Phase 2: data
python -m data_gen.generate --tiny     # 3-asset starter set -> data/tiny/
python -m data_gen.generate            # full fleet -> data/dev/, data/heldout/ (do NOT peek at heldout), data/assets.json
python -m data_gen.plot_assets         # eyeball every dev asset -> docs/plots/dev/
python -m data_gen.render_corpus       # regenerate work-order markdown from past_work_orders.json

## Phase 3: detection
python -m detection.run --report                                        # replay all dev assets vs dev labels
python -m detection.run --asset P-102 --now 2026-10-25T00:00           # print one Flag as JSON
(held-out data is refused unless --i-accept-peeking is passed; do not do that before Phase 10)
