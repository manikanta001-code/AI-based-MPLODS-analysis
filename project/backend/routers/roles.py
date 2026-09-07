"""
routers/roles.py
───────────────────
/api/roles/{role} — one call the frontend makes right after login to get
everything a role's landing dashboard needs in one round-trip: KPI
summary, top alerts, and the role-appropriate comparison table (Ministry
gets state rankings, State gets district rankings, MP/District get their
own top categories instead since a "ranking of 1" isn't useful).

ACCESS RULE: a user can only ever fetch THEIR OWN role's bundle. Ministry
is the only role allowed to pass query params to preview a specific
state/mp/district's bundle (e.g. for drilling in from the national view).
"""

import sys
import os

from fastapi import APIRouter, Depends, HTTPException, Query

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from auth import get_current_user, CurrentUser
from db_utils import build_where_clause, run_query, query_works, clean_nan

router = APIRouter(prefix="/api/roles", tags=["roles"])

VALID_ROLES = {"mp", "state", "district", "ministry"}


def _summary(filters: dict):
    where_sql, params = build_where_clause(filters)
    sql = f"""
        SELECT
            COUNT(*) AS total_works,
            SUM(sanction_amount) AS total_sanctioned_amount,
            SUM(amount_disbursed) AS total_disbursed_amount,
            SUM(is_completed) AS completed_works,
            SUM(CASE WHEN risk_band = 'High' THEN 1 ELSE 0 END) AS flagged_high,
            SUM(CASE WHEN delay_risk_pct >= 70 THEN 1 ELSE 0 END) AS predicted_delayed_count,
            AVG(risk_score) AS avg_risk_score
        FROM work_risk_scores {where_sql}
    """
    df = run_query(sql, params)
    row = df.iloc[0].to_dict()
    total_sanctioned = row["total_sanctioned_amount"] or 0
    total_disbursed = row["total_disbursed_amount"] or 0
    row["utilization_pct"] = (total_disbursed / total_sanctioned * 100) if total_sanctioned else 0
    return row


@router.get("/{role}")
def get_role_dashboard(
    role: str,
    state: str | None = None,
    mp_name: str | None = None,
    ida: str | None = Query(None, description="District/Implementing Agency"),
    user: CurrentUser = Depends(get_current_user),
):
    if role not in VALID_ROLES:
        raise HTTPException(status_code=404, detail=f"Unknown role '{role}'. Must be one of {VALID_ROLES}")

    if role != user.role and user.role != "ministry":
        raise HTTPException(
            status_code=403,
            detail=f"Your account is role '{user.role}' — you cannot access the '{role}' dashboard",
        )

    # Determine the effective scope for this bundle
    filters = {}
    if role == "mp":
        filters["mp_name"] = user.scope if user.role == "mp" else mp_name
    elif role == "state":
        filters["state"] = user.scope if user.role == "state" else state
    elif role == "district":
        filters["ida"] = user.scope if user.role == "district" else ida
    # role == "ministry": no forced filter -> national view

    filters = {k: v for k, v in filters.items() if v}

    bundle = {"role": role, "scope": filters, "summary": _summary(filters)}

    # Top 5 alerts within scope
    df_alerts, total_alerts = query_works(filters, page=1, page_size=5, sort_by="risk_score", sort_dir="desc")
    bundle["top_alerts"] = df_alerts[[
        "work_id", "state", "mp_name", "work_category", "sanction_amount", "risk_score", "risk_band", "risk_reasons"
    ]].to_dict(orient="records") if not df_alerts.empty else []
    bundle["total_flagged_high"] = bundle["summary"]["flagged_high"]

    # Role-appropriate comparison table
    if role == "ministry":
        bundle["ranking"] = run_query("""
            SELECT state, COUNT(*) AS work_count, SUM(sanction_amount) AS total_sanctioned,
                   SUM(CASE WHEN risk_band='High' THEN 1 ELSE 0 END) AS flagged_high_count
            FROM work_risk_scores GROUP BY state ORDER BY flagged_high_count DESC LIMIT 10
        """).to_dict(orient="records")
        bundle["ranking_label"] = "Top states by high-risk work count"
    elif role == "state":
        where_sql, params = build_where_clause(filters)
        bundle["ranking"] = run_query(f"""
            SELECT ida AS district_agency, COUNT(*) AS work_count, SUM(sanction_amount) AS total_sanctioned,
                   SUM(CASE WHEN risk_band='High' THEN 1 ELSE 0 END) AS flagged_high_count
            FROM work_risk_scores {where_sql} GROUP BY ida ORDER BY flagged_high_count DESC LIMIT 10
        """, params).to_dict(orient="records")
        bundle["ranking_label"] = "Top districts by high-risk work count"
    else:
        where_sql, params = build_where_clause(filters)
        bundle["ranking"] = run_query(f"""
            SELECT work_category, COUNT(*) AS work_count, SUM(sanction_amount) AS total_sanctioned,
                   AVG(risk_score) AS avg_risk_score
            FROM work_risk_scores {where_sql} GROUP BY work_category ORDER BY total_sanctioned DESC LIMIT 10
        """, params).to_dict(orient="records")
        bundle["ranking_label"] = "Work categories by total sanctioned amount"

    return bundle
