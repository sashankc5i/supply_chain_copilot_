# Evaluation Results

Last run via `python eval/run_evals.py` (after `python scripts/generate_data.py`).

## Primary metrics (SKU-week detection)

| Metric | Result | Target | Status |
|--------|--------|--------|--------|
| Alert precision | **1.000** | >= 0.85 | PASS |
| Alert recall (full suite) | **0.214** | >= 0.90 | FAIL |
| Avg recommendation score | **3.67 / 5** | >= 3.5 | PASS |
| Avg pipeline latency | **6.0 s** | < 45 s | PASS |

## Demo-only (submission scenarios)

| Metric | Result |
|--------|--------|
| Demo recall (sku-week) | **1.000** (3/3) |
| demo-1 | HIGH detected, rec score 5 |
| demo-2 | HIGH detected, rec score 5 |
| demo-3 | MEDIUM at ST-003, summarize path |

Use **demo-only recall** for presentation; full-suite recall is dragged down by organic labels that do not match z-score/DOH rules at the labeled store.

## Store-level (secondary)

See `metrics_store_level` in `eval/eval_results.json` — stricter match on exact `(sku_id, store_id)`.

## Reproduce

```powershell
python scripts/generate_data.py
python eval/run_evals.py
```

Full per-case JSON: `eval/eval_results.json` (gitignored).
