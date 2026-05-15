"""POST /whatif -- proxy to what_if_sim tool."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.tools.what_if_sim import what_if_sim

router = APIRouter()


class WhatIfRequest(BaseModel):
    sku_id: str
    store_id: str
    qty_adjust: int = 0
    promo_shift_days: int = 0


@router.post("/whatif")
def post_whatif(body: WhatIfRequest) -> dict:
    fn = what_if_sim
    if hasattr(fn, "invoke"):
        return fn.invoke(body.model_dump())
    return fn(
        sku_id=body.sku_id,
        store_id=body.store_id,
        qty_adjust=body.qty_adjust,
        promo_shift_days=body.promo_shift_days,
    )
