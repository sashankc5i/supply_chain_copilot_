# Supply Chain Command Center Copilot

LangGraph agent that detects demand anomalies, retrieves evidence, diagnoses root cause, recommends actions, critiques constraints, and escalates high-impact decisions to a human (HITL).

## Quick start

```powershell
cd d:\gen_ai_project
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Generate synthetic CSVs (once)
python scripts/generate_data.py

# Optional: week dimension table
python scripts/generate_dim_date.py

# Tests
pytest tests/ -v

# Dashboard (HITL approve works in-process)
streamlit run dashboard/app.py

# Optional API (what-if proxy, external clients)
uvicorn src.api.main:app --reload --port 8000
```

Configure Azure OpenAI in `.env` (see `.env.example`):

- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_API_VERSION`
- `AZURE_OPENAI_DEPLOYMENT_NAME`

Verify LLM: `python src/graph/llm.py`

## Demo scenarios

| Scenario | Week start | Expected path |
|----------|------------|----------------|
| Demo 1 — SKU-1042 spike (West) | 2026-01-12 | HIGH → evidence → diagnose → recommend → critique → **HITL approve** |
| Demo 2 — SKU-0217 drop (South) | 2026-01-26 | HIGH → supplier delay → recommend → critique (may retry) → HITL |
| Demo 3 — SKU-0089 borderline (East) | 2026-02-09 | LOW/MEDIUM → **summarize** (no HITL) |

Presenter walkthrough: [`demo_script.md`](demo_script.md)

## HITL and action log

1. Run **Demo 1** or **Demo 2** on the Command Center page.  
2. When critique approves, click **Approve** / **Reject** / **Edit** (no FastAPI required).  
3. Rows append to `data/runtime/action_log.csv`.  
4. View history on the **hitl approval** Streamlit page.

## Evaluation

```powershell
python eval/run_evals.py
```

Summary: [`eval_results.md`](eval_results.md)

## Architecture

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for graph topology, state schema, routing, and data model.

## Project layout

```
src/graph/          LangGraph nodes, prompts, tracing
src/tools/          CSV-backed evidence tools
src/api/            FastAPI (approval, alerts, whatif)
dashboard/          Streamlit UI
eval/               Evaluation harness
data/raw/           Synthetic CSVs
data/runtime/       action_log, node_latency, checkpoints
scripts/            Data generators
```

## Commands reference

| Command | Purpose |
|---------|---------|
| `python -m src.graph.graph` | Print graph ASCII |
| `pytest tests/ -v` | Unit tests |
| `streamlit run dashboard/app.py` | Command Center |
| `python eval/run_evals.py` | Metrics run |

## Known limitations

- CSV-only data (no warehouse DB).  
- LangSmith not used; traces in `data/runtime/node_latency.csv`.  
- Organic eval recall is strict per `(sku, store)` — see `eval_results.md`.  
- SQLite checkpointer shared at `data/runtime/checkpoints.db` for graph pause/resume.
