# Use Case Scorecard - Predictive Maintenance Agent
Scale: 1-5, where 5 is MOST favourable for building (so "risk 5" = low risk).
Agent type: Assist, then Act | Model approach: routed (open for routine, frontier for hard) | Size: Medium

| Criterion | Score | Reason |
|---|---|---|
| Business value | 5 | Unplanned downtime is costly; early warning converts emergency repairs into planned ones. |
| Data readiness | 4 | Sensor/maintenance data exists in real plants; here fully synthetic with known ground truth. Real data would need cleaning. |
| Integration effort | 4 | Only a small self-built SQLite app behind our own MCP server. Real CMMS/SCADA integration would be harder. |
| Risk | 4 | Agent can only create drafts; planner approves everything; detection is deterministic. Residual risk: bad explanation. |
| Model fit | 4 | LLM is good at explaining from documents; we deliberately keep it away from numeric detection. |
| Cost per task | 4 | Open model for routine flags; frontier only for high-risk/multi-signal. Cost is logged per flag. |

TODO (team): argue each score for 5 minutes, and check with your mentor whether Parkar has its own definition of the six criteria.
