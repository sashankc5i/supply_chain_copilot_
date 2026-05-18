# Demo Script — Supply Chain Command Center Copilot

Step-by-step presenter walkthrough for the three live demo scenarios.
Estimated duration: ~12 minutes.

---

## Pre-demo checklist (5 min before)

```powershell
cd d:\gen_ai_project
.\.venv\Scripts\Activate.ps1

# Terminal 1 — Streamlit dashboard (HITL approve works in-process, no API required)
streamlit run dashboard/app.py

# Terminal 2 (optional) — FastAPI for /whatif and external API clients
uvicorn src.api.main:app --reload --port 8000
```

- Open browser to http://localhost:8501  
- Confirm the sidebar shows all demo scenarios and the ▶ Run pipeline button is visible.  
- Optional: confirm http://localhost:8000/docs loads if running FastAPI (what-if page can use local tool fallback).

---

## Scenario 1 — Promo spike + heatwave (SKU-1042, West, Week 87)

**Expected path:** HIGH → evidence (promo + weather) → diagnose → recommend `transfer_inventory` → critique **approves** → HITL **approve** → action logged.

### Steps

1. In the sidebar, select **"Demo 1 — SKU-1042 spike (West, Wk87)"**.
2. Click **▶ Run pipeline**.
3. Watch the spinner — pipeline completes in ~15-30s.
4. **Point at:** KPI row — `Alerts` count, `HIGH` count, `Latency` in ms.
5. **Alerts column:** scroll to SKU-1042 cards. Note severity badge = HIGH and z-score > +3.
6. **Evidence panel:** 4 cards appear — promo (confidence ~0.85), weather (~0.75), supplier, demand. Point at the confidence progress bars.
7. **Root-cause hypotheses:** `promo_effect` ranks first, followed by `weather_event`.
8. **Recommendations table:** top action = `transfer_inventory`, cost ~$1,200-2,000, DOH improvement ~3-5 days.
9. **⏸ HITL banner** appears at the top. Click **Approve** in the recommendation table.
10. Confirm: green banner "✅ Action **approved** — logged to action_log.csv."
11. Open **Pipeline metadata** expander → `approval_status: approved`.
12. Open **🔍 Run breakdown** expander → show node-by-node timing bars: detect, retrieve_evidence, diagnose, recommend, critique, escalate.

**Talking points:**
- "The promo + heatwave combination drove a 120% WoW demand spike but DOH fell to ~3 days."
- "The graph called 4 evidence tools *in parallel* — retrieve_evidence ran in under 8s."
- "Critique is deterministic — no LLM cost. It confirmed the transfer won't breach DC safety-stock."
- "One click to approve; the decision is permanently logged with a timestamp."

---

## Scenario 2 — Supplier delay (SKU-0217, South, Week 89)

**Expected path:** HIGH → evidence (supplier delay) → diagnose → recommend `expedite_order` → critique **rejects** (lead time > days-to-stockout) → retry → re-recommend → HITL **edit qty** → critique **approves** → action logged.

### Steps

1. Select **"Demo 2 — SKU-0217 drop (South, Wk89)"**.
2. Click **▶ Run pipeline**.
3. **Point at:** `retry_count: 1` in Pipeline metadata — the self-correction loop ran.
4. **Root-cause hypotheses:** `supplier_delay` first.
5. **Recommendations table:** may show `expedite_order` (re-recommended after critique rejection) or `transfer_inventory` as fallback.
6. **⏸ HITL banner** appears. Click **Edit** → change qty in the edit modal → submit.
7. Confirm: blue banner "✏️ Action **edited** — re-critiqued with new params."
8. **Pipeline metadata** → `approval_status: edited`.

**Talking points:**
- "DOH fell to ~4.8 days due to a supplier flagged with active delay."
- "The first recommendation exceeded supplier lead time — critique caught it without any LLM cost."
- "The retry loop is capped at 1 attempt so the graph can't spin forever."
- "Edit flow: the operator adjusts qty, the graph resumes from critique — no re-diagnosis needed."

---

## Scenario 3 — Borderline MEDIUM / fast path (SKU-0089, East, Week 91)

**Expected path:** MEDIUM → summarize fast path, **no HITL**.

### Steps

1. Select **"Demo 3 — SKU-0089 borderline (East, Wk91)"**.
2. Click **▶ Run pipeline**.
3. **No HITL banner** — pipeline ends immediately at `summarize`.
4. **Exceptions / summary** box shows the 2-sentence operator summary.
5. **KPIs:** `HIGH = 0`, `Recs = 0`.
6. **Pipeline metadata:** `approval_status: n/a`.

**Talking points:**
- "DOH is ~18 days — comfortably above the safety threshold. No action warranted."
- "The summarize fast path costs one cheap LLM call (no tool calls, no critique). Total latency <5s."
- "This is the 90% case in production — the copilot stays out of the way when nothing is wrong."

---

## What-if panel demo (bonus, 2 min)

1. Navigate to **What-If Simulator** page in the left sidebar.
2. Set SKU = `SKU-0217`, Store = `ST-002`.
3. Drag **Qty Adjust** to `+500`.
4. Click **▶ Run Simulation**.
5. Point at the side-by-side bar chart: baseline DOH ~4.8 d → projected ~7.2 d, stockout prob drops.
6. Try `promo_shift_days = +7` — show DOH improves further.

---

## Expected output verbatim (Scenario 1)

| Field                | Expected value                                      |
|----------------------|-----------------------------------------------------|
| detected severity    | HIGH                                                |
| top cause_type       | promo_effect                                        |
| top action_type      | transfer_inventory                                  |
| critique verdict     | approved                                            |
| approval_status      | approved (after presenter clicks Approve)           |
| latency (pipeline)   | 15–35 s (LLM calls dominate)                        |
| detect latency       | < 5 s                                               |
| retrieve_evidence    | < 8 s (parallel tool calls)                         |

---

## Fallback if FastAPI is down

The dashboard still shows alerts, evidence, and recommendations. HITL
Approve/Reject/Edit buttons will show a "Connection refused" error — explain
that the approval endpoint requires the FastAPI server and start it live:

```powershell
uvicorn src.api.main:app --reload --port 8000
```

Then re-run the scenario.
