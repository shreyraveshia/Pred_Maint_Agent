# Acceptance Targets (agreed Day 1; tested in the evaluation report on the 20% held-out set)

| # | Metric | Target |
|---|---|---|
| 1 | Detection recall (seeded faults found) | >= 90% |
| 2 | Detection precision | >= 85% |
| 3 | False-alarm rate on healthy/decoy assets | <= 10% |
| 4 | Median lead time before threshold breach / failure | >= 3 days |
| 5 | Citation correctness (cited IDs exist AND were retrieved AND support claim) | >= 95% |
| 6 | Explanations without evidence or explicit "no evidence" notice | 0 |
| 7 | Confirmed/predicted mislabels | 0 |
| 8 | Write actions without human approval | 0 |
| 9 | Pipeline crashes under injected failures (API down, bad JSON, tool error) | 0 |
| 10 | Average cost per flag, routed vs frontier-only | routed lower; report % saving |

Rule: targets are fixed now. If we miss one, we report it honestly. We never retune on the held-out set.
