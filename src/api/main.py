"""FastAPI entry -- HITL approval, alerts, what-if proxy.

Run:
    uvicorn src.api.main:app --reload --port 8000
"""
from __future__ import annotations

if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from src.api.routes import alerts, approval, whatif  # noqa: E402

app = FastAPI(title="Supply Chain Copilot API", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(approval.router, tags=["approval"])
app.include_router(alerts.router, tags=["alerts"])
app.include_router(whatif.router, tags=["whatif"])


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
