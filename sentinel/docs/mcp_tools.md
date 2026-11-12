# MCP Tool Contract (our own server; allow-list enforced; agent has no other route to the DB)

| Tool | Access | Input | Output |
|---|---|---|---|
| get_asset | read | asset_id: str | asset_id, name, type, location, criticality (1-3), last_service_date, installed_date |
| get_history | read | asset_id: str, limit: int = 10 | list of past work orders: wo_id, date, fault, action_taken, parts_used, status |
| check_spares | read | part_id: str | part_id, description, qty_in_stock, reorder_level, lead_time_days |
| create_draft_work_order | draft_write | WorkOrderDraft (contracts/models.py) | wo_id, status="draft" |

Rules
1. status is hardcoded to "draft" inside the server. The client cannot set it.
2. There is NO tool to approve, edit, reject or delete. Those live only in the dashboard (human) layer.
3. Every tool validates input with Pydantic and returns a structured error, never a stack trace.
4. Every call is written to the audit log with actor = sentinel-agent.
5. Unknown tool names are rejected via contracts/permissions.py.
