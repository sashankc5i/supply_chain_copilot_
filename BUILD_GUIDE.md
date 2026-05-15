# Build Guide — LangGraph Supply Chain Command Center Copilot

A phase-by-phase manual for building the agentic supply-chain copilot specified
in `supply_chain_copilot_complete.docx`. Every phase lists its goal, features
delivered, per-owner tasks with detailed explanations, the files created, the
commands to run, and the verification step that proves the phase is done.

> Read [interface_spec.md](interface_spec.md) for the locked contracts between
> components. Read the plan at
> `C:\Users\Sashank.S\.claude\plans\now-give-me-a-temporal-scone.md` for the
> condensed checklist version of this guide.

---

## Table of Contents

- [Project at a glance](#project-at-a-glance)
- [Owner tracks](#owner-tracks)
- [Phase 0 — Environment setup](#phase-0--environment-setup)
- [Phase 1 — Day 1 (Thursday): Kickoff + Scaffolding](#phase-1--day-1-thursday-kickoff--scaffolding)
- [Phase 2 — Day 2 (Friday): First Real Nodes + Tools](#phase-2--day-2-friday-first-real-nodes--tools)
- [Phase 3 — Day 3 (Saturday): Recommend + Critique + HITL + Routing](#phase-3--day-3-saturday-recommend--critique--hitl--routing)
- [Phase 4 — Day 4 (Sunday): Evaluation + Trace Quality + Polish](#phase-4--day-4-sunday-evaluation--trace-quality--polish)
- [Phase 5 — Day 5 (Monday): Dry Run + Docs](#phase-5--day-5-monday-dry-run--docs)
- [Phase 6 — Day 6 (Tuesday): Submission](#phase-6--day-6-tuesday-submission)
- [Quick command reference](#quick-command-reference)
- [Troubleshooting](#troubleshooting)

---

## Project at a glance

The copilot ingests demand, inventory, promo, supplier, and weather signals;
detects anomalies; calls evidence tools in parallel; asks an LLM to diagnose
the root cause; recommends ranked actions; checks them against business
constraints; and routes high-cost actions to a human approver — with full
LangSmith trace explainability.

**Graph topology:**

```
START -> detect ─┬─> retrieve_evidence -> diagnose -> recommend -> critique ─┬─> escalate ─┬─> END
                 │                                       ▲                    │             │
                 │                                       └────────────────────┘             │
                 │                                       (retry once if rejected)            │
                 │                                                                          │
                 └─> summarize ─> END                                          └─> critique (on edit)
```

**Tech stack:**

| Layer            | Choice                                                      |
|------------------|-------------------------------------------------------------|
| LLM              | Azure OpenAI `gpt-4o-mini` via `langchain-openai.AzureChatOpenAI`, `temperature=0` |
| Graph framework  | LangGraph 0.2+                                              |
| Tracing          | none (LangSmith intentionally omitted)                      |
| Data             | pandas + CSV (no DB)                                        |
| API              | FastAPI                                                     |
| Dashboard        | Streamlit                                                   |
| Data generation  | Python + numpy + Faker, seed 42                             |

---

## Owner tracks

The build is structured so 5 engineers can work in parallel. Every phase below
lists tasks bucketed by owner.

| Owner   | Responsibility                                                                |
|---------|-------------------------------------------------------------------------------|
| Lead    | Architecture, routing logic, retrieve_evidence, prompts, demo polish, docs    |
| P2      | Synthetic data, metrics utilities, evaluation harness                         |
| P3      | LangGraph wiring, detect/diagnose/recommend/critique/summarize nodes, traces  |
| P4      | Tool layer, what-if sim, HITL interrupt + FastAPI approval endpoint           |
| P5      | Streamlit dashboard — alert list, evidence panel, HITL modal, what-if panel   |

---

## Phase 0 — Environment setup

**Goal:** every engineer has a working Python environment with all dependencies
installed and API keys configured.

### Tasks

1. **Install Python 3.10+** (script tested on 3.14).
2. **Clone the repo** and `cd` into the project root.
3. **Create a virtualenv** so deps don't pollute the system Python.
4. **Install dependencies** from `requirements.txt`.
5. **Create the `.env` file** with API keys (gitignored; never commit).
6. **Set `PYTHONPATH`** so absolute `src.*` imports work in your IDE.

### Commands (PowerShell on Windows)

```powershell
cd d:\gen_ai_project

# Create + activate venv
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install deps
pip install -r requirements.txt

# Create .env at the project root (Azure OpenAI; LangSmith not used)
@'
AZURE_OPENAI_ENDPOINT="https://<your-resource>.openai.azure.com/"
AZURE_OPENAI_OPENAI_ENDPOINT="https://<your-resource>.openai.azure.com/openai/v1/"
AZURE_OPENAI_API_KEY="<your-azure-openai-api-key>"
AZURE_OPENAI_MODEL_NAME="gpt-4o-mini"
AZURE_OPENAI_DEPLOYMENT_NAME="gpt-4o-mini"
AZURE_OPENAI_API_VERSION="2024-08-01-preview"
'@ | Out-File -FilePath .env -Encoding utf8
```

### Verification

```powershell
python -c "import langgraph, langchain_openai, pandas, streamlit; print('ok')"
```

Then verify the LLM is reachable (one round-trip, costs a few tokens):

```powershell
python src/graph/llm.py
```

Prints `LLM configured: ...` followed by the model's `ok` response.

Prints `ok` — all imports resolved.

---

## Phase 1 — Day 1 (Thursday): Kickoff + Scaffolding

### Goal
Every owner unblocked with stubs that pass type checks. No real logic yet —
the point is to lock interfaces so Day 2 can parallelise without integration
breaks.

### Features delivered
- All 8 synthetic CSVs generated and saved under `data/raw/` and
  `data/processed/`.
- Cached pandas loaders for every CSV.
- LangGraph topology compiled with placeholder nodes.
- 6 LLM-callable tool stubs returning realistic mock data.
- Static HTML dashboard wireframe showing every UI element with mocked content.
- Locked interface spec (`interface_spec.md`) — no rename without sign-off.

### Tasks

#### [All] Repo setup (~2h)

**What it is:** create the folder tree per design doc §3, write `.gitignore`,
install deps in a shared venv.

**Why it matters:** consistent layout means everyone's imports work the same
way. A `.gitignore` early prevents the 4 MB generated CSVs from ever entering
git history.

**Files created:**
- [.gitignore](.gitignore) — excludes `data/raw/`, `data/runtime/`,
  `data/processed/`, `eval/eval_results.json`, `.env`, `__pycache__/`,
  `.venv/`, etc.
- [requirements.txt](requirements.txt) — pinned versions for pandas,
  langgraph, langchain-anthropic, fastapi, streamlit, faker.

#### [P2] Run data generator + ship loaders

**What it is:** execute `scripts/generate_data.py` to produce the 7 raw CSVs +
1 labeled-anomalies file + 1 empty action log. Then build
`src/data/loaders.py` so every downstream module reads CSVs through one
cached import.

**Why it matters:** the synthetic data is the *ground truth* the copilot
reasons over. The script bakes in three deliberate scenarios (promo spike,
supplier delay, false alert) so the LLM has matching signals to diagnose. The
loaders use `@lru_cache(maxsize=1)` so the 52k-row demand CSV is parsed once
per process — anything else makes the graph slow.

**Files created:**
- [scripts/generate_data.py](scripts/generate_data.py) — single-file generator,
  seed 42.
- [data/raw/sku_master.csv](data/raw/sku_master.csv) — 200 rows.
- [data/raw/location_master.csv](data/raw/location_master.csv) — 60 rows.
- [data/raw/promotion_calendar.csv](data/raw/promotion_calendar.csv) — ~800 rows.
- [data/raw/weather_events.csv](data/raw/weather_events.csv) — ~500 rows.
- [data/raw/supplier_data.csv](data/raw/supplier_data.csv) — 600 rows.
- [data/raw/demand_history.csv](data/raw/demand_history.csv) — ~52,000 rows.
- [data/raw/inventory_snapshot.csv](data/raw/inventory_snapshot.csv) — 12,000 rows.
- [data/processed/anomalies_labeled.csv](data/processed/anomalies_labeled.csv) —
  ground-truth labels for eval.
- [data/runtime/action_log.csv](data/runtime/action_log.csv) — header-only.
- [data/reference/](data/reference/) — 11 borrowed artifacts from the
  official P5 dataset (HITL thresholds, eval benchmark, gold-standard
  scenario traces, state-schema reference, what-if expected output, demo
  narrative). **Reference-only** — IDs don't align with our generated data;
  read via `load_reference(filename)`. See
  [data/reference/README.md](data/reference/README.md) for the catalogue.
- [src/data/loaders.py](src/data/loaders.py) — `load_skus`, `load_locations`,
  `load_demand`, `load_inventory`, `load_promos`, `load_weather`,
  `load_suppliers`, `load_labeled_anomalies`, `load_action_log`,
  `reload_all`.

**Commands:**
```powershell
python scripts/generate_data.py
```
Should print row counts and demo-scenario sanity values (SKU-1042 ~+120% WoW,
SKU-0217 DOH ~4.8d, SKU-0089 DOH ~18d).

#### [P3] State schema + empty graph

**What it is:** define the `SupplyChainState` TypedDict in `state.py` per
design doc §7.1, then assemble the graph topology in `graph.py` with
no-op nodes and conditional edges already wired.

**Why it matters:** the state schema is the contract every node agrees to.
Locking it Day 1 means P3, P4, and P5 can stub the same field names and
the integration on Day 3 has nothing to debug. The empty graph proves the
topology is structurally valid before anyone writes real logic.

**Files created:**
- [src/graph/state.py](src/graph/state.py) — `SupplyChainState` TypedDict,
  plus nested `DemandSignal`, `EvidenceBlock`, `RootCauseHypothesis`,
  `Recommendation`, `CritiqueResult`.
- [src/graph/graph.py](src/graph/graph.py) — `StateGraph(SupplyChainState)`
  with 7 placeholder nodes (`detect`, `retrieve_evidence`, `diagnose`,
  `recommend`, `critique`, `escalate`, `summarize`), 3 routing functions
  (`route_after_detect`, `route_after_critique`, `route_after_escalate`),
  compiled to `app`.

**Commands:**
```powershell
python src/graph/graph.py
```
Prints ASCII art of the graph topology.

#### [P4] Tool stubs + API contracts

**What it is:** create 6 `@tool`-decorated functions under `src/tools/` with
the exact signatures locked Day 1. Each returns hardcoded data matching the
agreed output schema.

**Why it matters:** the diagnose LLM will eventually call these tools by name
and rely on their docstrings to know what they do. Locking signatures
*before* writing the real CSV-reading logic lets P3 build the diagnose node
in parallel against the stubs. When P4 swaps the body for real data on Day 2,
diagnose keeps working because the schema didn't change.

**Files created:**
- [src/tools/demand_lookup.py](src/tools/demand_lookup.py) — trailing-N-week
  demand series + WoW delta + z-score.
- [src/tools/inventory_lookup.py](src/tools/inventory_lookup.py) — on-hand,
  DOH, reorder point, safety stock.
- [src/tools/promo_calendar.py](src/tools/promo_calendar.py) — active promos
  for a SKU/region/week.
- [src/tools/weather_events.py](src/tools/weather_events.py) — regional
  weather/holiday/festival events.
- [src/tools/supplier_delays.py](src/tools/supplier_delays.py) — supplier
  roster with active delay flags.
- [src/tools/what_if_sim.py](src/tools/what_if_sim.py) — projected DOH +
  stockout prob under a qty/promo tweak.
- [src/tools/__init__.py](src/tools/__init__.py) — exports `ALL_TOOLS` list.

#### [P5] Dashboard wireframe

**What it is:** a single static HTML file with embedded CSS showing every
panel the production dashboard will have, populated with mock data for
SKU-1042.

**Why it matters:** wireframing before wiring forces decisions on layout,
density, color-coding (severity badges, confidence bars, verdict colors),
and HITL modal flow. P3 and P4 see the UI early so the state schema and
API responses include the fields the UI needs.

**Files created:**
- [dashboard/dashboard.html](dashboard/dashboard.html) — header KPIs (alerts
  today, stockout risk, HITL queue, latency), 3-column main (alerts list /
  evidence + diagnosis + recommendations / HITL modal overlay).

**Commands:**
```powershell
# Open in browser
start dashboard\dashboard.html
```

#### [Lead] Architecture review + interface lock (end of day)

**What it is:** review every stub committed by EOD, then write
[interface_spec.md](interface_spec.md) — the binding contract for state
field names, tool I/O dicts, FastAPI payload shapes, and date conventions.

**Why it matters:** "we'll just refactor later" is how integration breaks at
3 AM the day before a demo. The spec freezes contracts Day 1; renames after
that require Lead approval and a spec update.

**Files created:**
- [interface_spec.md](interface_spec.md) — sections for state TypedDicts,
  tool signatures, HITL approval payload, action_log row shape, determinism
  rules, verification command.

### End-of-Phase-1 verification

```powershell
python src/graph/graph.py
```

Prints the graph ASCII. Then in a Python REPL:
```python
from src.graph.graph import app
state = app.invoke({"run_id": "test-0001"})
print(state.keys())
```
Returns without error — passthrough nodes populate placeholder fields.

---

## Phase 2 — Day 2 (Friday): First Real Nodes + Tools

### Goal
detect + diagnose run on real synthetic data. All 6 tools read real CSVs.
Streamlit can show a live alert list from `state["demand_signals"]`.

### Features delivered
- Z-score-based anomaly detection on real demand history.
- DOH-driven severity classification (HIGH / MEDIUM / LOW).
- Parallel evidence retrieval (promo + weather + supplier + demand) via
  `asyncio.gather`.
- LLM-powered root-cause diagnosis returning structured JSON.
- Metrics module (`compute_doh`, `stockout_prob`, `service_level`) with pytest
  coverage.
- Dashboard alert list populated from a real graph invocation.

### Tasks

#### [P3] detect + diagnose nodes

**What it is:**
- `detect` reads the current-week slice of `demand_history.csv`, computes
  z-score vs trailing 8-week mean per (sku_id, store_id), joins with
  `inventory_snapshot.csv` to compute DOH, and assigns severity:
  HIGH (DOH<5), MEDIUM (5≤DOH≤10), LOW (DOH>10). Sets `anomaly_type` to
  `spike`, `drop`, `flat_line` (units=0), or `normal`.
- `diagnose` builds a structured prompt from the evidence dict + flagged
  demand_signal, calls Azure OpenAI `gpt-4o-mini` (via
  `src.graph.llm.get_llm()`, `temperature=0`), and parses JSON output into
  `RootCauseHypothesis` dicts.

**Why it matters:** detect is pure pandas — no LLM cost, must run in <5s on
200 SKUs × 50 stores. Diagnose is where the LLM earns its keep: it reads
4 evidence sources and synthesises a ranked hypothesis list. Forcing JSON
output (via prompt + schema example) is the standard trick to avoid
unparseable model responses.

**Files created:**
- `src/graph/nodes/detect.py` — `detect(state) -> dict` returning
  `{"demand_signals": [...], "inventory_positions": {...}}`.
- `src/graph/nodes/diagnose.py` — `diagnose(state) -> dict` returning
  `{"root_cause_hypotheses": [...]}`.
- `src/graph/prompts/diagnose_prompt.txt` — system prompt with the 5 cause
  types, JSON schema example, and chain-of-thought hint.

**Then:** edit `src/graph/graph.py` to import the real `detect` and
`diagnose` functions instead of the placeholders.

#### [P4] Real tool implementations

**What it is:** replace each stub body with a real CSV read via
`src/data/loaders.py`. Keep the function signature and output schema
identical.

**Why it matters:** because schemas were locked Day 1, P3 doesn't have to
change a single import. Tool calls just start returning realistic data.

**Files modified:**
- `src/tools/demand_lookup.py` — slice `load_demand()` for the (sku, store)
  pair, compute WoW delta and rolling z-score on the trailing window.
- `src/tools/inventory_lookup.py` — point lookup on `load_inventory()`.
- `src/tools/promo_calendar.py` — filter `load_promos()` by sku + region +
  date-range overlap.
- `src/tools/weather_events.py` — filter `load_weather()` by region + week.
- `src/tools/supplier_delays.py` — filter `load_suppliers()` by sku, sort
  primary first.
- `src/tools/what_if_sim.py` — apply linear delta to baseline DOH from
  inventory lookup.

#### [P2] Metrics module

**What it is:** three small pure-Python utilities used by detect, critique,
and the eval harness. Tests live under `tests/test_metrics.py`.

**Why it matters:** these are pulled out of the nodes so the eval harness
can score detection precision/recall against the same DOH formula the
graph uses. Drift here would silently invalidate eval numbers.

**Files created:**
- `src/metrics/compute_doh.py` —
  `compute_doh(units_on_hand: float, avg_daily_demand: float) -> float`.
- `src/metrics/stockout_prob.py` —
  `stockout_prob(doh: float, horizon_days: int = 14) -> float` (clipped
  `1 - doh/horizon`).
- `src/metrics/service_level.py` — `fill_rate(demand_df, sku, store,
  weeks=8) -> float`.
- `tests/test_metrics.py` — pytest for each function (edge: zero demand,
  zero on-hand, doh > horizon).

**Commands:**
```powershell
pytest tests/ -v
```

#### [P5] Dashboard ↔ graph wiring

**What it is:** create `dashboard/app.py` (Streamlit entry). Import
`src.graph.graph.app`, call `app.invoke({"run_id": ...})`, render the
returned `state["demand_signals"]` as an alert list.

**Why it matters:** replaces the static HTML mock with a live view that
re-runs on Streamlit's auto-refresh.

**Files created:**
- `dashboard/app.py` — Streamlit entry point.
- `dashboard/pages/command_center.py` — alert list with severity / region /
  category filters.
- `dashboard/components/alert_card.py` — reusable alert row component.

**Commands:**
```powershell
streamlit run dashboard/app.py
```

#### [Lead] Prompts + retrieve_evidence node

**What it is:** write the diagnose system prompt (forces JSON, lists 5 cause
types, includes the demo-scenario style of reasoning). Then build the
`retrieve_evidence` node that calls all 4 tools in parallel via
`asyncio.gather` and assembles the structured evidence dict.

**Why it matters:** retrieve_evidence is the most performance-sensitive node
because it's where latency stacks up. Calling 4 tools serially is ~4× slower
than parallel. The structured evidence dict (with `source` attribution and
`confidence`) is what makes the diagnose LLM's output trustworthy.

**Files created:**
- `src/graph/prompts/diagnose_prompt.txt` — system prompt template.
- `src/graph/prompts/recommend_prompt.txt` — placeholder for Day 3 (Lead
  pre-writes it so P3 isn't blocked).
- `src/graph/nodes/retrieve_evidence.py` — `async def
  retrieve_evidence(state) -> dict` returning `{"evidence": {"promo": ...,
  "weather": ..., "supplier": ..., "demand": ...}}`.

### End-of-Phase-2 verification

```python
from src.graph.graph import app
state = app.invoke({"sku_id": "SKU-1042", "store_id": "ST-007",
                    "week_start": "2026-01-12", "run_id": "demo-1"})
print(state["demand_signals"][0]["severity"])  # HIGH
print(state["root_cause_hypotheses"][0]["cause_type"])
```
Should print `HIGH` and a cause type citing promo or weather.

---

## Phase 3 — Day 3 (Saturday): Recommend + Critique + HITL + Routing

### Goal
End-to-end pipeline runnable. LOW severity → summarize. HIGH severity →
diagnose → recommend → critique → escalate → HITL → log.

### Features delivered
- LLM-generated ranked recommendations with cost, confidence, and DOH delta.
- Deterministic constraint checker (no LLM) with 4 rule families: safety-stock
  floor, supplier lead time, MOQ, budget cap.
- One-retry loop when critique rejects (state.retry_count guard).
- HITL graph interrupt + FastAPI approval endpoint with approve/reject/edit
  flows.
- action_log.csv appended on every approve/reject/edit.
- Full evidence + recommendations panels in the dashboard.

### Tasks

#### [P3] recommend + critique nodes

**What it is:**
- `recommend`: LLM call using `recommend_prompt.txt`. Reads the dominant
  root cause from state, generates 2-3 ranked actions with `action_type`,
  `params`, `cost_usd`, `confidence`, `doh_improvement_days`.
- `critique`: pure Python deterministic checker (no LLM). Walks each
  recommendation against 4 constraint families and outputs
  `{verdict, top_action, violated_constraint, reason}`.

**Why it matters:** recommend is creative work — LLM picks between transfer /
expedite / promo reduction / wait. Critique is *not* creative — it's the
fail-safe that prevents the LLM from suggesting a transfer that would
breach DC safety stock. Keeping it deterministic makes it cheap, fast, and
unit-testable.

**Constraint rules (in critique):**
1. `transfer_inventory` → source DC DOH after move ≥ safety_stock floor.
2. `expedite_order` → supplier `lead_time_days` < days-to-stockout.
3. `expedite_order` → ordered qty ≥ `moq_units`.
4. Any action → `cost_usd` ≤ budget cap (default $5,000).

**Files created:**
- `src/graph/nodes/recommend.py`.
- `src/graph/nodes/critique.py`.
- `src/graph/nodes/summarize.py` — short LLM call for LOW severity + data
  glitches.
- `src/graph/prompts/recommend_prompt.txt` — already drafted Day 2 by Lead.
- `tests/test_critique.py` — pytest covering each constraint family.

#### [Lead] Routing logic

**What it is:** wire conditional edges in `src/graph/graph.py` per
design doc §7.3 (route_after_detect, route_after_critique,
route_after_escalate).

**Why it matters:** routing is what makes this an *agentic* graph instead of
a linear pipeline. The retry loop on critique-rejected (max 1 attempt) is
the system's self-correction proof point in the demo.

**Files modified:**
- `src/graph/graph.py` — replace placeholder edges with real conditional
  routing.

#### [P4] HITL approval flow

**What it is:**
- `escalate` node calls LangGraph's `interrupt()` primitive with a payload
  containing the top action, cost, and run_id.
- FastAPI service exposes `POST /approval/{run_id}` accepting
  `{decision: "approve"|"reject"|"edit", params, reason}`.
- On `approve`/`reject`: log a row to `data/runtime/action_log.csv`.
- On `edit`: update `state["recommendations"][0]["params"]` and resume the
  graph routing back into `critique`.

**Why it matters:** HITL is the highest-impact moment in the demo. The
`interrupt()` + `resume()` pattern is what makes "pause the graph mid-flow
and wait for a human" possible. Without this, the system is just an
expensive recommender.

**Files created:**
- `src/graph/nodes/escalate.py`.
- `src/api/main.py` — FastAPI app with CORS + LangGraph checkpointer.
- `src/api/routes/approval.py` — `POST /approval/{run_id}`.
- `src/api/routes/alerts.py` — `GET /alerts` returning current alert list.
- `src/api/routes/whatif.py` — `POST /whatif` proxying to `what_if_sim`.

**Commands:**
```powershell
uvicorn src.api.main:app --reload --port 8000
```

#### [P5] Evidence + recommendation panels

**What it is:** real React-/Streamlit-rendered evidence cards (one per
source: promo, weather, supplier, demand) with confidence bars, plus a
ranked recommendation table with `Approve / Reject / Edit` buttons calling
the FastAPI approval endpoint.

**Files created:**
- `dashboard/components/evidence_panel.py`.
- `dashboard/components/recommendation_table.py`.
- `dashboard/pages/hitl_approval.py` — pending tab + resolved tab.

#### [All] Integration checkpoint (1h, end of day)

**What it is:** run all 3 demo scenarios end-to-end together. Fix integration
breaks. Lock the 3 scenarios for the demo.

### End-of-Phase-3 verification

All 3 demo scenarios reach their expected terminal state:

| Scenario                      | Expected path                                                                       |
|-------------------------------|--------------------------------------------------------------------------------------|
| SKU-1042 / West / Week 87     | HIGH → evidence (promo+weather) → diagnose → recommend transfer → critique approves → HITL approve → action logged. |
| SKU-0217 / South / Week 89    | HIGH → evidence (supplier delay) → diagnose → recommend expedite+transfer → critique rejects expedite (lead time) → re-recommend → HITL edit qty → critique approves → action logged. |
| SKU-0089 / East / Week 91     | MEDIUM → summarize fast path, no HITL.                                              |

---

## Phase 4 — Day 4 (Sunday): Evaluation + Trace Quality + Polish

### Goal
Eval harness produces real precision/recall numbers. Every demo scenario
has a clean LangSmith trace with node-level I/O. What-if panel works.
Dashboard is presentation-ready.

### Features delivered
- `eval/run_evals.py` writes `eval_results.json` with precision, recall, LLM
  judge score, and per-node latency.
- Local node-level timing logs persisted to `data/runtime/node_latency.csv`
  (substitute for LangSmith — see Phase 4 [P3]).
- Interactive what-if simulation panel.
- Polished dashboard with loading states, approval confirmations.

### Tasks

#### [P2] Evaluation harness

**What it is:** a script that loops over labeled test cases, invokes the
graph, compares predicted severity against `is_anomaly` ground truth, and
scores recommendation quality via an LLM-as-judge rubric.

**Why it matters:** "we built it" → "we built it and here are the numbers"
is the difference between a prototype and an enterprise-grade demo.

**Metrics computed:**
- Alert precision (TP / (TP+FP)) — target ≥0.85.
- Alert recall (TP / (TP+FN)) — target ≥0.90.
- Recommendation correctness — LLM judge 1-5 score, target mean ≥3.5.
- Per-node latency — target detect <5s, retrieve_evidence <8s (parallel),
  diagnose <10s, full pipeline <45s.

**Files created:**
- `eval/test_cases.json` — labeled scenarios (3 demo + 10-15 organic
  anomalies pulled from `anomalies_labeled.csv`).
- `eval/rubric.py` — `score_recommendation(recs, hypotheses,
  ground_truth_cause) -> int`. Uses `src.graph.llm.get_llm()` (Azure OpenAI
  gpt-4o-mini) as judge.
- `eval/run_evals.py` — main runner, writes `eval/eval_results.json`.

**Commands:**
```powershell
python eval/run_evals.py
```

#### [P3] Local trace quality (substitute for LangSmith)

**What it is:** since LangSmith isn't being used, instrument every node to
log node-name, input-size, output-size, latency, and routing decision to
`data/runtime/node_latency.csv`. The dashboard surfaces this as a per-alert
"Run breakdown" panel so evaluators can still see the agent's decisions.

**Why it matters:** evaluators care about *what the agent decided and why*.
Without a hosted trace UI, the dashboard becomes the explainability surface
— the run breakdown shows each node's input summary, output summary, and
the routing decision that followed.

**How:**
- Add a small `src/graph/tracing.py` helper exposing
  `@log_node(name)` — a decorator that times the call, captures
  `state.run_id`, summarises in/out keys, and appends a row to
  `data/runtime/node_latency.csv`.
- Wrap every node function with `@log_node("detect")`,
  `@log_node("diagnose")`, etc.
- Build `dashboard/components/run_breakdown.py` to render the per-run rows
  as an ordered list with timing bars.

**Files created:**
- `src/graph/tracing.py` — `log_node` decorator.
- `dashboard/components/run_breakdown.py`.

#### [Lead] Demo polish

**What it is:** craft 3 scenarios with compelling, deterministic numbers
(the data already provides these). Write a presenter script: which alert
to click, what to point at in the trace, expected outputs verbatim.

**Files created:**
- `demo_script.md` — step-by-step walkthrough for the presenter.

#### [P5] Dashboard polish + HITL UX

**What it is:** loading spinners during graph.invoke, error states for tool
failures, per-alert "Run breakdown" panel rendering rows from
`data/runtime/node_latency.csv`, approval confirmation modal.

#### [P4] What-if simulation UI

**What it is:** sliders for `qty_adjust` (-1000 to +2000) and
`promo_shift_days` (-14 to +14). Calls `what_if_sim` tool via FastAPI.
Side-by-side baseline-vs-projected stockout-prob bar chart.

**Files created:**
- `dashboard/pages/what_if.py`.

### End-of-Phase-4 verification

```powershell
python eval/run_evals.py
```

Should write `eval/eval_results.json` with precision ≥0.85, recall ≥0.90,
avg recommendation score ≥3.5/5, avg latency <45s/run.

---

## Phase 5 — Day 5 (Monday): Dry Run + Docs

### Goal
Two clean dry-runs in a row. README + ARCHITECTURE written. Eval numbers
locked.

### Tasks

#### [All] Two full dry runs (~3h)

**What it is:** run the complete demo end-to-end twice. Log every issue.
Fix the priority ones — anything that breaks the HITL flow is critical;
what-if panel is cuttable if it's wobbly.

#### [Lead] Docs

**Files created:**
- `README.md` — quick start (5 commands), demo walkthrough, architecture
  diagram (ASCII or screenshot of LangSmith), known limitations, future
  scope. **Evaluators read this first.**
- `ARCHITECTURE.md` — graph topology diagram, state schema, routing table,
  prompt strategy, tool layer, HITL flow sequence diagram.

#### [P2] Eval results writeup

**Files created:**
- `eval_results.md` — final numbers in a results table, plus 1-2 paragraphs
  on what they mean.

### End-of-Phase-5 verification

A fresh clone smoke test passes:
```powershell
git clone <repo> fresh && cd fresh
python -m venv .venv && .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/generate_data.py
streamlit run dashboard/app.py
```
Dashboard loads, alert list populates, all 3 demo scenarios work.

---

## Phase 6 — Day 6 (Tuesday): Submission

### Goal
Submit on time.

### Tasks

- **9 AM**: Code freeze. No new features. Bug fixes only if a dry run breaks.
- **10 AM**: Final README pass. Make sure quick-start commands are exactly
  the ones in this file.
- **11 AM**: One last rehearsal by the presenter.
- **Noon**: Submit.

---

## Quick command reference

```powershell
# 1. Setup (Phase 0)
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. Generate synthetic data (Phase 1, runs once)
python scripts/generate_data.py

# 3. Inspect graph topology (Phase 1 verification)
python src/graph/graph.py

# 4. Run unit tests (Phase 2-3)
pytest tests/ -v

# 5. Start the FastAPI backend (Phase 3 onward)
uvicorn src.api.main:app --reload --port 8000

# 6. Start the dashboard (Phase 2 onward)
streamlit run dashboard/app.py

# 7. Run evaluation harness (Phase 4)
python eval/run_evals.py

# 8. Open static wireframe (Phase 1)
start dashboard\dashboard.html

# 9. Sanity-check the LLM client (Phase 0+ verification, one round-trip)
python src/graph/llm.py
```

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'src'`

The script was launched directly without the project root on `sys.path`.

Fix: run from the project root with `python -m`:
```powershell
cd d:\gen_ai_project
python -m src.graph.graph
```

Or use the self-bootstrap pattern (already in `graph.py`):
```python
if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
```

### `pandas.errors.ParserError` while loading CSVs

Re-run the generator — the CSVs may have been truncated mid-write:
```powershell
python scripts/generate_data.py
```

### Azure OpenAI errors

**`RuntimeError: Missing required env vars: ...`** —
`src/graph/llm.py` couldn't find one of `AZURE_OPENAI_ENDPOINT`,
`AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_API_VERSION`,
`AZURE_OPENAI_DEPLOYMENT_NAME`. Confirm `.env` has all four and that
`load_dotenv()` ran (entry points include it; in a REPL you must call
`from dotenv import load_dotenv; load_dotenv()` once).

**`openai.AuthenticationError: 401`** — the key is wrong or has been rotated.
Regenerate in Azure Portal → your OpenAI resource → Keys and Endpoint.

**`openai.NotFoundError: The API deployment for this resource does not exist`** —
`AZURE_OPENAI_DEPLOYMENT_NAME` doesn't match a deployment under the
configured endpoint. Check Azure Portal → Deployments.

**`openai.BadRequestError: API version not supported`** —
bump `AZURE_OPENAI_API_VERSION` to a value listed in your resource's
"API versions" tab.

### Streamlit shows "Connection refused" on /approval

FastAPI isn't running. Start it in a separate terminal:
```powershell
uvicorn src.api.main:app --reload --port 8000
```

### `interrupt()` not pausing the graph

Make sure you're using a checkpointer when compiling the graph:
```python
from langgraph.checkpoint.memory import MemorySaver
app = g.compile(checkpointer=MemorySaver())
```
Without a checkpointer, `interrupt()` raises but doesn't pause cleanly.

### Demo numbers don't match the design doc

The data generator uses `np.random.seed(42)`. If you edited the script, the
seed sequence shifted — re-run the original to restore deterministic demos.

---

*Generated for the LangGraph Supply Chain Command Center Copilot project.
Source of truth: [supply_chain_copilot_complete.docx](supply_chain_copilot_complete.docx).*
