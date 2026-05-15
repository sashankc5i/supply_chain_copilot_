# Interface Spec — Day 1 Lock

This document pins every cross-team contract for the supply-chain copilot.
After EOD Thursday no field is renamed, no type changes silently. If a shape
must change, it goes through the Lead and this file gets updated first.

Source of truth for schemas:
- [src/graph/state.py](src/graph/state.py) — TypedDicts for the graph state
- [src/tools/*.py](src/tools/) — `@tool` docstrings for tool I/O
- This file — narrative + payloads not captured in code

---

## 1. Graph state (`SupplyChainState`)

Top-level keys (all optional via `total=False`, populated incrementally):

| Key                     | Type                            | Populated by         |
|-------------------------|----------------------------------|----------------------|
| `demand_signals`        | `list[DemandSignal]`            | `detect`             |
| `inventory_positions`   | `dict[sku_id, dict[loc_id, row]]` | `detect`           |
| `service_levels`        | `dict[sku_id, float]`           | `detect` (optional)  |
| `evidence`              | `dict[str, EvidenceBlock]`      | `retrieve_evidence`  |
| `root_cause_hypotheses` | `list[RootCauseHypothesis]`     | `diagnose`           |
| `recommendations`       | `list[Recommendation]`          | `recommend`          |
| `critique_result`       | `CritiqueResult`                | `critique`           |
| `approval_status`       | `"pending"\|"approved"\|"rejected"\|"edited"\|"n/a"` | `escalate` |
| `exceptions`            | `list[str]`                     | `summarize` (append) |
| `retry_count`           | `int`                           | router (incremented) |
| `run_id`                | `str` (UUID4 hex)               | caller of `app.invoke` |

### Nested dict shapes

```python
DemandSignal = {
  "sku_id": "SKU-1042",
  "store_id": "ST-007",
  "week_start": "2026-05-11",        # ISO date
  "units_sold": 253,
  "wow_delta_pct": 120.0,
  "zscore": 3.4,
  "region": "West",
  "severity": "HIGH",                # HIGH | MEDIUM | LOW
  "anomaly_type": "spike",           # spike | drop | flat_line | normal
}

EvidenceBlock = {
  "source": "promotion_calendar.csv",
  "data": [ ... ] | { ... },         # whatever the tool returned
  "estimated_impact_pct": 40.0,
  "confidence": 0.95,
}

RootCauseHypothesis = {
  "cause_type": "promo_effect",      # promo_effect | weather_event |
                                     # supplier_delay | competitor | data_anomaly
  "confidence": 0.85,
  "explanation": "2x BOGO promo explains majority of the spike...",
  "evidence_sources": ["promo", "demand"],
}

Recommendation = {
  "action_type": "transfer_inventory",  # transfer_inventory | expedite_order |
                                        # reduce_promo | wait_and_watch
  "params": {                            # action-type-specific
    "qty_units": 400,
    "source_locations": ["DC-002", "DC-005"],
    "destination_location_id": "ST-007",
    "timeline_days": 3,
  },
  "cost_usd": 1240.0,
  "confidence": 0.88,
  "doh_improvement_days": 5.4,
}

CritiqueResult = {
  "verdict": "approved",             # approved | rejected | flagged
  "top_action": Recommendation | None,
  "violated_constraint": "",         # "" if approved
  "reason": "All constraints satisfied.",
}
```

---

## 2. Tool contracts

All tools are `@tool`-decorated functions in [src/tools/](src/tools/). Each
docstring carries the binding I/O schema. Summary table:

| Tool               | Signature                                                                                                | Returns      |
|--------------------|-----------------------------------------------------------------------------------------------------------|--------------|
| `demand_lookup`    | `(sku_id, store_id, weeks=8, anchor_week: Optional[str] = None)` — `anchor_week` is an ISO "YYYY-MM-DD". When given, returns the `weeks` rows ending at this date (inclusive); used by `retrieve_evidence` to pull context AROUND the anomaly week, not the latest data. | `dict` |
| `inventory_lookup` | `(sku_id, location_id)`                                                    | `dict`       |
| `promo_calendar`   | `(sku_id, region, week_start)` — `week_start` is ISO `"YYYY-MM-DD"`        | `list[dict]` |
| `weather_events`   | `(region, week_start)`                                                     | `list[dict]` |
| `supplier_delays`  | `(sku_id)`                                                                 | `list[dict]` |
| `what_if_sim`      | `(sku_id, store_id, qty_adjust=0, promo_shift_days=0)`                     | `dict`       |

**Date convention:** every date crossing a tool boundary is an ISO string
`"YYYY-MM-DD"` (not a `datetime` object). Tools that read CSVs convert
internally.

**Region values:** `"North" | "South" | "East" | "West" | "Central"` — exactly
those spellings.

**Categories:** `"Beverage" | "Snack" | "Dairy" | "Frozen" | "Bakery" |
"PersonalCare" | "HouseholdCare"`. `affected_categories` in
`weather_events` returns a `list[str]` from this set.

---

## 3. FastAPI HITL approval contract (P4)

### POST `/approval/{run_id}`

Called by the dashboard when an operator decides on a pending HITL action.

**Request body:**
```json
{
  "decision": "approve" | "reject" | "edit",
  "params": { ... },         // required when decision == "edit"; overrides Recommendation.params
  "reason": "..."            // required when decision == "reject" or "edit"
}
```

**Response:**
```json
{
  "run_id": "5f...",
  "status": "resumed" | "completed" | "error",
  "next_node": "critique" | "END" | null,
  "message": "..."
}
```

Server behaviour:
- `approve` → graph.resume() → action logged to `data/runtime/action_log.csv`, branch ends.
- `reject` → log row with `rejection_reason`, branch ends.
- `edit`   → update `state['recommendations'][0]['params']`, route back to `critique`.

### GET `/alerts`
Returns the current list of active alerts (post-detect) for the alert-list panel.
Shape: `list[DemandSignal]` with an extra `run_id` field per row.

### POST `/whatif`
Body: `{sku_id, store_id, qty_adjust, promo_shift_days}` → returns what_if_sim output dict.

---

## 4. `action_log.csv` row shape (runtime-appended)

| Column              | Example                                                  |
|---------------------|----------------------------------------------------------|
| `run_id`            | `5f8a2c1d...`                                            |
| `sku_id`            | `SKU-1042`                                               |
| `action_type`       | `transfer_inventory`                                     |
| `recommendation`    | JSON string of the full `Recommendation` dict            |
| `approval_status`   | `approved` / `rejected` / `edited-then-approved`         |
| `approver`          | operator handle, e.g. `sashank.s@c5i.ai`                 |
| `rejection_reason`  | free text or empty                                       |
| `timestamp`         | ISO 8601 in UTC                                          |

---

## 5. Determinism rules

- `np.random.seed(42)` everywhere stochastic.
- LLM: Azure OpenAI `gpt-4o-mini` via `src.graph.llm.get_llm()`,
  `temperature=0` for `diagnose`, `recommend`, and `eval/rubric.py` judge.
- Anchor "this week" = `date(2026, 5, 11)` (matches `scripts/generate_data.py`).
- All ISO dates in UTC; no timezone-aware datetimes cross tool boundaries.
- LangSmith tracing is not used; per-node latency + routing decisions are
  appended to `data/runtime/node_latency.csv` instead.

---

## 6. Verification at end of Phase 1

```
python -m src.graph.graph
```
Prints the topology ASCII. Then in a Python REPL:

```python
from src.graph.graph import app
state = app.invoke({"run_id": "test-0001"})
print(state.keys())
```

Should return without error. Real signals appear once Phase 2 wires the
detect node to `src.data.loaders.load_demand`.
