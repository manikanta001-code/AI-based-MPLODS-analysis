"""
db_utils.py
─────────────
Shared helpers for querying the `work_risk_scores` table (built by
ml/train.py) with dynamic, SAFELY-PARAMETERIZED filters, plus the
role-scope enforcement used by every router.
"""

import math

import pandas as pd
from sqlalchemy import text

from database import engine

WORKS_TABLE = "work_risk_scores"


def clean_nan(obj):
    """Recursively replace float NaN with None. Needed because Starlette's
    default JSONResponse uses strict json.dumps(allow_nan=False) — a NaN
    anywhere in a response (e.g. 0/0 in a utilization-% calc for a state
    with zero disbursed amount, like Andaman & Nicobar Islands in this
    dataset) crashes the endpoint with a 500 otherwise. Every router wraps
    its return value with this before sending it back."""
    if isinstance(obj, dict):
        return {k: clean_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean_nan(v) for v in obj]
    if isinstance(obj, float) and math.isnan(obj):
        return None
    return obj


def enforce_scope(filters: dict, user) -> dict:
    """
    Overrides (not merely validates) the relevant filter for non-ministry
    roles, using the scope baked into their JWT. A client-supplied value for
    that same filter is silently replaced — this is what makes the scoping
    a real access control, not just a UI convenience. See auth.py docstring.
    """
    filters = dict(filters)
    if user.role == "mp":
        filters["mp_name"] = user.scope
    elif user.role == "state":
        filters["state"] = user.scope
    elif user.role == "district":
        filters["ida"] = user.scope
    # ministry: no forced filter, client-supplied filters (if any) pass through
    return filters


def build_where_clause(filters: dict):
    """
    filters keys understood: state, ida, work_category, work_status, risk_band,
    mp_name, search (matches work_id OR work_description), min_risk_score.
    Returns (where_sql, params) for use in a parameterized query.
    """
    clauses = []
    params = {}

    simple_eq_columns = {
        "state": "state",
        "ida": "ida",
        "work_category": "work_category",
        "work_status": "work_status",
        "risk_band": "risk_band",
        "mp_name": "mp_name",
        "constituency": "constituency",
    }
    for key, col in simple_eq_columns.items():
        val = filters.get(key)
        if val:
            clauses.append(f"{col} = :{key}")
            params[key] = val

    if filters.get("search"):
        clauses.append("(work_id LIKE :search OR work_description LIKE :search)")
        params["search"] = f"%{filters['search']}%"

    if filters.get("min_risk_score") is not None:
        clauses.append("risk_score >= :min_risk_score")
        params["min_risk_score"] = filters["min_risk_score"]

    if filters.get("is_completed") is not None:
        clauses.append("is_completed = :is_completed")
        params["is_completed"] = int(filters["is_completed"])

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return where_sql, params


ALLOWED_SORT_COLUMNS = {
    "risk_score", "sanction_amount", "amount_disbursed", "anomaly_score",
    "delay_risk_pct", "cost_risk_pct", "duplicate_score", "sanction_date", "work_id",
}


def query_works(filters: dict, page: int = 1, page_size: int = 25,
                 sort_by: str = "risk_score", sort_dir: str = "desc"):
    where_sql, params = build_where_clause(filters)
    sort_by = sort_by if sort_by in ALLOWED_SORT_COLUMNS else "risk_score"
    sort_dir = "DESC" if str(sort_dir).lower() != "asc" else "ASC"

    count_sql = text(f"SELECT COUNT(*) as n FROM {WORKS_TABLE} {where_sql}")
    with engine.connect() as conn:
        total = conn.execute(count_sql, params).scalar()

    offset = (page - 1) * page_size
    data_sql = text(
        f"SELECT * FROM {WORKS_TABLE} {where_sql} "
        f"ORDER BY {sort_by} {sort_dir} LIMIT :limit OFFSET :offset"
    )
    query_params = {**params, "limit": page_size, "offset": offset}
    df = pd.read_sql(data_sql, engine, params=query_params)

    return df, total


def query_one_work(work_id: str):
    sql = text(f"SELECT * FROM {WORKS_TABLE} WHERE work_id = :work_id")
    df = pd.read_sql(sql, engine, params={"work_id": work_id})
    return df


def run_query(sql: str, params: dict = None) -> pd.DataFrame:
    return pd.read_sql(text(sql), engine, params=params or {})
