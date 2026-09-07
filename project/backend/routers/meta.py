"""
routers/meta.py
──────────────────
Small lookup endpoints the frontend uses to populate dropdowns and filter
controls (state/category/status filters on the Works & Alerts pages, the
"select MP" control on the Ministry/State drill-down views). No auth
required — these only return distinct label lists, not work data.
"""

from fastapi import APIRouter

from db_utils import run_query

router = APIRouter(prefix="/api/meta", tags=["meta"])


@router.get("/states")
def list_states():
    df = run_query("SELECT DISTINCT state FROM work_risk_scores WHERE state IS NOT NULL ORDER BY state")
    return df["state"].tolist()


@router.get("/mps")
def list_mps():
    df = run_query("SELECT DISTINCT mp_name FROM work_risk_scores WHERE mp_name IS NOT NULL ORDER BY mp_name")
    return df["mp_name"].tolist()


@router.get("/districts")
def list_districts():
    """Returns {label, value} pairs — value is the exact `ida` string routers
    filter on; label strips the "(DISTRICT MAGISTRATE ...)" suffix for display."""
    df = run_query("SELECT DISTINCT ida FROM work_risk_scores WHERE ida IS NOT NULL AND ida != 'Unknown' ORDER BY ida")
    return [
        {"value": ida, "label": ida.split("(")[0].strip()}
        for ida in df["ida"].tolist()
    ]


@router.get("/categories")
def list_categories():
    df = run_query("SELECT DISTINCT work_category FROM work_risk_scores WHERE work_category IS NOT NULL ORDER BY work_category")
    return df["work_category"].tolist()


@router.get("/statuses")
def list_statuses():
    df = run_query("SELECT DISTINCT work_status FROM work_risk_scores WHERE work_status IS NOT NULL ORDER BY work_status")
    return df["work_status"].tolist()
