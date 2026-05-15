# `data/reference/` — Borrowed artifacts from the official P5 dataset

These files were extracted from `P5_LangGraph_SupplyChain_SyntheticDataset.zip`
(the design doc's official reference dataset, ~16 weeks × 10 SKUs × 10 stores
across 5 deliberate anomaly scenarios). They are **reference-only** — kept
here as design inspiration, evaluation templates, and gold-standard outputs.

> ⚠️ **The IDs in these files do not align with our generated data.** The P5
> dataset uses `SKU-001..010` (3-digit, sequential) and `STR-001..010`. Our
> generated data uses `SKU-0089..1042` (sparse 4-digit) and `ST-001..050`.
> Do not row-concat these CSVs with files in `data/raw/`.

## What each file is for

| File                                | Reference use during build                                                                |
|-------------------------------------|--------------------------------------------------------------------------------------------|
| `P5_DATASET_DESCRIPTION.md`         | Narrative for the 5 anomaly scenarios (SC-001..SC-005) + demo flow. Read this for Phase 4 demo polish. |
| `service_level_targets.{csv,json}`  | HITL threshold rules (auto-approve < ₹25K, branch mgr < ₹100K, SCM Director > ₹100K), per-SKU criticality tiers (CRITICAL/HIGH/MEDIUM), stockout tolerance hours. **Adapt the bands into `src/graph/nodes/critique.py` (Phase 3) — convert INR to USD or keep INR.** |
| `sc_eval_benchmark.{csv,json}`      | 12 hand-crafted eval cases mapped to demo steps. Use as inspiration for `eval/test_cases.json` (Phase 4). Steal the `expected_routing`, `expected_critique_output`, `expected_hitl_action` column structure. |
| `state_schema.json`                 | Official state-schema reference. Compare against `src/graph/state.py`; field names are subtly different (`exceptions` vs `demand_signals`, etc.) — pick whichever spelling you prefer per field, but **lock it in [interface_spec.md](../../interface_spec.md)**. |
| `langgraph_scenario_traces.json`    | Gold-standard node-by-node traces for all 5 scenarios — what diagnose/recommend/critique *should* output. Use these as **few-shot examples** in `src/graph/prompts/*.txt` (Phase 2 Lead) and as ground truth for `eval/rubric.py` (Phase 4). |
| `agent_trace_log.csv`               | 85 rows of per-tool-call metadata (latency, tokens, cost, status). Schema reference for our local `node_latency.csv` (Phase 4 [P3]). |
| `whatif_simulation_results.csv`     | Expected output schema for `what_if_sim` tool — cover-before, cover-after, cost, stockout-avoided. Match this shape when implementing the real tool body (Phase 2 [P4]). |
| `shipment_data.csv`                 | Per-shipment table with planned vs actual arrival, carrier, status. We don't have this table; included if we ever extend to a shipment tool. Reference-only for now. |
| `metadata_registry.csv`             | File index for the P5 dataset — informational only. |

## How to load

`src/data/loaders.py` exposes a generic helper:

```python
from src.data.loaders import load_reference

slt = load_reference("service_level_targets.csv")
eval_set = load_reference("sc_eval_benchmark.csv")
traces = load_reference("langgraph_scenario_traces.json")  # returns dict
```

## What NOT to do

- ❌ `pd.concat([load_inventory(), load_reference("shipment_data.csv")])` — incompatible schemas, different units.
- ❌ Pass SKU-001..010 IDs to our graph — `detect` will return empty results because those SKUs don't exist in `sku_master.csv`.
- ❌ Mix INR and USD in cost calculations — pick one currency in `critique.py` budget rules.

## What TO do

- ✅ Read `P5_DATASET_DESCRIPTION.md` once at the start of Phase 4 for demo polish.
- ✅ Lift HITL threshold bands from `service_level_targets.csv` (convert INR if needed) into `critique.py` constraint rules.
- ✅ Copy the column structure of `sc_eval_benchmark.csv` for `eval/test_cases.json`, but replace SKUs/scenarios with ours.
- ✅ Use `langgraph_scenario_traces.json` as few-shot prompting material — show the LLM what good output looks like.
