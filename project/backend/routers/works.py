"""
routers/works.py
───────────────────
/api/works       — paginated, filterable list of works (Alerts page, work
                    tables on every dashboard, the underlying data behind
                    every chart)
/api/works/{id}  — full detail for one work (Project Detail page)
"""

import math
import sys
import os

from fastapi import APIRouter, Depends, HTTPException, Query

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from auth import get_current_user, CurrentUser
from db_utils import enforce_scope, query_works, query_one_work, clean_nan

router = APIRouter(prefix="/api/works", tags=["works"])


@router.get("")
def list_works(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    state: str | None = None,
    ida: str | None = Query(None, description="District/Implementing Agency"),
    work_category: str | None = None,
    work_status: str | None = None,
    risk_band: str | None = Query(None, description="High | Medium | Low"),
    mp_name: str | None = None,
    constituency: str | None = None,
    search: str | None = Query(None, description="Matches Work ID or description text"),
    min_risk_score: float | None = None,
    is_completed: bool | None = None,
    sort_by: str = "risk_score",
    sort_dir: str = "desc",
    user: CurrentUser = Depends(get_current_user),
):
    filters = {
        "state": state, "ida": ida, "work_category": work_category, "work_status": work_status,
        "risk_band": risk_band, "mp_name": mp_name, "constituency": constituency, "search": search,
        "min_risk_score": min_risk_score, "is_completed": is_completed,
    }
    filters = enforce_scope(filters, user)

    df, total = query_works(filters, page=page, page_size=page_size, sort_by=sort_by, sort_dir=sort_dir)

    return clean_nan({
        "page": page,
        "page_size": page_size,
        "total": int(total),
        "total_pages": math.ceil(total / page_size) if page_size else 0,
        "items": df.to_dict(orient="records"),
    })


@router.get("/{work_id}")
def get_work(work_id: str, user: CurrentUser = Depends(get_current_user)):
    df = query_one_work(work_id)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"Work ID {work_id} not found")

    row = df.iloc[0]
    # Scope check: non-ministry users can't fetch a work outside their own scope,
    # even though they might guess a valid Work ID.
    if user.role == "mp" and row["mp_name"] != user.scope:
        raise HTTPException(status_code=403, detail="This work is outside your scope")
    if user.role == "state" and row["state"] != user.scope:
        raise HTTPException(status_code=403, detail="This work is outside your scope")
    if user.role == "district" and row["ida"] != user.scope:
        raise HTTPException(status_code=403, detail="This work is outside your scope")

    return clean_nan(df.to_dict(orient="records")[0])
