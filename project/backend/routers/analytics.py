"""
routers/analytics.py
───────────────────────
Aggregate analytics behind every dashboard's KPI cards and charts.
  /api/analytics/summary           — KPI cards (any role, auto-scoped)
  /api/analytics/state-rankings    — Ministry only (cross-state comparison)
  /api/analytics/district-rankings — Ministry + State (cross-district within a state)
  /api/analytics/category-stats    — any role, auto-scoped
  /api/analytics/yearly-trends     — any role, auto-scoped
"""

import sys
import os

from fastapi import APIRouter, Depends, Query

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from auth import get_current_user, require_roles, CurrentUser
from db_utils import enforce_scope, build_where_clause, run_query, clean_nan

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/summary")
def summary(user: CurrentUser = Depends(get_current_user)):
    filters = enforce_scope({}, user)
    where_sql, params = build_where_clause(filters)

    sql = f"""
        SELECT
            COUNT(*) AS total_works,
            SUM(sanction_amount) AS total_sanctioned_amount,
            SUM(amount_disbursed) AS total_disbursed_amount,
            SUM(is_completed) AS completed_works,
            SUM(CASE WHEN is_completed = 0 THEN 1 ELSE 0 END) AS ongoing_works,
            SUM(CASE WHEN risk_band = 'High' THEN 1 ELSE 0 END) AS flagged_high,
            SUM(CASE WHEN risk_band = 'Medium' THEN 1 ELSE 0 END) AS flagged_medium,
            SUM(CASE WHEN risk_band = 'Low' THEN 1 ELSE 0 END) AS flagged_low,
            SUM(CASE WHEN delay_risk_pct >= 70 THEN 1 ELSE 0 END) AS predicted_delayed_count,
            AVG(risk_score) AS avg_risk_score
        FROM work_risk_scores
        {where_sql}
    """
    df = run_query(sql, params)
    row = df.iloc[0].to_dict()

    total_sanctioned = row["total_sanctioned_amount"] or 0
    total_disbursed = row["total_disbursed_amount"] or 0
    row["utilization_pct"] = (total_disbursed / total_sanctioned * 100) if total_sanctioned else 0
    return clean_nan(row)


@router.get("/state-rankings")
def state_rankings(user: CurrentUser = Depends(require_roles("ministry"))):
    sql = """
        SELECT
            state,
            COUNT(*) AS work_count,
            SUM(sanction_amount) AS total_sanctioned,
            SUM(amount_disbursed) AS total_disbursed,
            SUM(CASE WHEN risk_band = 'High' THEN 1 ELSE 0 END) AS flagged_high_count,
            AVG(risk_score) AS avg_risk_score
        FROM work_risk_scores
        GROUP BY state
        ORDER BY flagged_high_count DESC
    """
    df = run_query(sql)
    df["utilization_pct"] = df.apply(
        lambda r: (r["total_disbursed"] / r["total_sanctioned"] * 100) if r["total_sanctioned"] else 0, axis=1
    )
    return clean_nan(df.to_dict(orient="records"))


@router.get("/district-rankings")
def district_rankings(
    state: str | None = None,
    user: CurrentUser = Depends(require_roles("ministry", "state")),
):
    filters = {}
    if user.role == "state":
        filters["state"] = user.scope
    elif state:
        filters["state"] = state
    where_sql, params = build_where_clause(filters)

    sql = f"""
        SELECT
            ida AS district_agency,
            state,
            COUNT(*) AS work_count,
            SUM(sanction_amount) AS total_sanctioned,
            SUM(amount_disbursed) AS total_disbursed,
            SUM(CASE WHEN risk_band = 'High' THEN 1 ELSE 0 END) AS flagged_high_count,
            AVG(risk_score) AS avg_risk_score
        FROM work_risk_scores
        {where_sql}
        GROUP BY ida, state
        ORDER BY flagged_high_count DESC
    """
    df = run_query(sql, params)
    return clean_nan(df.to_dict(orient="records"))


@router.get("/category-stats")
def category_stats(user: CurrentUser = Depends(get_current_user)):
    filters = enforce_scope({}, user)
    where_sql, params = build_where_clause(filters)

    sql = f"""
        SELECT
            work_category,
            COUNT(*) AS work_count,
            SUM(sanction_amount) AS total_sanctioned,
            AVG(risk_score) AS avg_risk_score,
            SUM(CASE WHEN risk_band = 'High' THEN 1 ELSE 0 END) AS flagged_high_count
        FROM work_risk_scores
        {where_sql}
        GROUP BY work_category
        ORDER BY total_sanctioned DESC
    """
    df = run_query(sql, params)
    return clean_nan(df.to_dict(orient="records"))


@router.get("/yearly-trends")
def yearly_trends(user: CurrentUser = Depends(get_current_user)):
    filters = enforce_scope({}, user)
    where_sql, params = build_where_clause(filters)
    if where_sql:
        where_sql += " AND sanction_date IS NOT NULL"
    else:
        where_sql = "WHERE sanction_date IS NOT NULL"

    sql = f"""
        SELECT
            substr(sanction_date, 1, 4) AS year,
            COUNT(*) AS work_count,
            SUM(sanction_amount) AS total_sanctioned,
            SUM(amount_disbursed) AS total_disbursed,
            AVG(risk_score) AS avg_risk_score
        FROM work_risk_scores
        {where_sql}
        GROUP BY year
        ORDER BY year
    """
    df = run_query(sql, params)
    return clean_nan(df.to_dict(orient="records"))
