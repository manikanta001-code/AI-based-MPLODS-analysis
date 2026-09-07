"""
ml/scorer.py
──────────────
Scores NEWLY UPLOADED data with the already-trained .pkl models — no
retraining. This is what the judges' live demo hits: upload a fresh batch
of MPLADS works (same raw column format as Works_Sanctioned.csv) and get
back risk scores + plain-English reasons in seconds.

EXPECTED UPLOAD FORMAT: same raw columns as Works_Sanctioned.csv —
    Sl No., Work Category, Work, State, IDA, Hon'ble Members of Parliament,
    Constituency, Work description, Recommended date, Sanction Date,
    Sanction Amount ( ₹ ), Work Status
(column names are matched case-insensitively / with minor separator
tolerance — see COLUMN_ALIASES below — since real-world re-exports often
vary "Work Category" vs "Work category" etc.)

WHY WE JOIN NEW ROWS INTO THE HISTORICAL CONTEXT FIRST
  A single newly-uploaded work's "category z-score" or "% of this MP's
  allocation" is meaningless computed against itself alone — it needs the
  full historical population as a yardstick. So we load the existing
  works_sanctioned/completed/mp_allocations tables from SQLite, CONCAT the
  new rows on top, run the exact same compute_derived_features() used in
  training, then slice back out just the new rows for scoring. The
  categorical encoders, however, are NOT refit — we reuse the ones saved
  during training (fit=False) so a new row's "state_enc" etc. means the
  same thing the models were trained on.
"""

import os
import pickle
import re
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # backend/
from config import (
    ENCODER_PATH, RAW_DATE_FORMAT, RISK_WEIGHTS,
)
from database import engine
from etl.preprocess import WORK_ID_PATTERN, clean_amount, clean_text
from etl.feature_engine import (
    merge_sources, compute_derived_features, encode_categoricals, finalize_feature_matrix,
    FEATURE_COLUMNS, load_raw_tables,
)
from ml import anomaly_detector, delay_model, cost_model, duplicate_finder, explain

COLUMN_ALIASES = {
    "sl no.": "Sr. No.", "sl. no.": "Sr. No.", "sr no.": "Sr. No.", "sr. no.": "Sr. No.",
    "work category": "Work category", "work": "Work", "state": "State", "ida": "IDA",
    "hon'ble members of parliament": "Hon'ble Members of Parliament",
    "constituency": "Constituency", "work description": "Work description",
    "recommended date": "Recommended date", "sanction date": "Sanction Date",
    "sanction amount ( ₹ )": "Sanction Amount ( ₹ )", "sanction amount": "Sanction Amount ( ₹ )",
    "work status": "Work Status",
}


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    rename_map = {}
    for col in df.columns:
        key = col.strip().lower()
        if key in COLUMN_ALIASES:
            rename_map[col] = COLUMN_ALIASES[key]
    return df.rename(columns=rename_map)


REQUIRED_COLUMNS = [
    "Work category", "Work", "State", "IDA", "Hon'ble Members of Parliament",
    "Constituency", "Work description", "Recommended date", "Sanction Date",
    "Sanction Amount ( ₹ )", "Work Status",
]


def clean_uploaded_sanctioned(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Same cleaning rules as etl/preprocess.py's load_sanctioned(), applied to
    a freshly uploaded dataframe instead of the original training CSV."""
    df = _normalize_columns(raw_df)

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"Uploaded file is missing required columns: {missing}. "
            f"Expected the same format as Works_Sanctioned.csv."
        )

    if "Sr. No." in df.columns:
        df = df[df["Sr. No."] != "Grand Total"].copy()
    else:
        df = df.copy()
        df["Sr. No."] = range(1, len(df) + 1)

    df["work_id"] = df["Work"].apply(
        lambda w: (WORK_ID_PATTERN.match(w.strip()).group(1) if pd.notna(w) and WORK_ID_PATTERN.match(w.strip()) else None)
    )
    df["sanction_amount"] = clean_amount(df["Sanction Amount ( ₹ )"])
    df["recommended_date"] = pd.to_datetime(df["Recommended date"], format=RAW_DATE_FORMAT, errors="coerce")
    df["sanction_date"] = pd.to_datetime(df["Sanction Date"], format=RAW_DATE_FORMAT, errors="coerce")

    df["ida_missing"] = df["IDA"].isna() | (df["IDA"].astype(str).str.strip() == "")
    df["IDA"] = df["IDA"].fillna("Unknown")
    df.loc[df["IDA"].astype(str).str.strip() == "", "IDA"] = "Unknown"

    n_before = len(df)
    df = df.dropna(subset=["work_id", "sanction_amount"])
    df = df[df["sanction_amount"] > 0]
    n_dropped = n_before - len(df)

    if len(df) == 0:
        raise ValueError("No valid rows remained after cleaning the uploaded file — check the 'Work' column "
                          "format (expects e.g. 'WS/ MP620/2024-2025/133166-...') and Sanction Amount values.")

    out = pd.DataFrame({
        "work_id": df["work_id"],
        "sl_no": pd.to_numeric(df["Sr. No."], errors="coerce"),
        "work_raw": df["Work"],
        "work_category": clean_text(df["Work category"]),
        "state": clean_text(df["State"]),
        "ida": df["IDA"],
        "ida_missing": df["ida_missing"],
        "mp_name": clean_text(df["Hon'ble Members of Parliament"]),
        "constituency": clean_text(df["Constituency"]),
        "work_description": clean_text(df["Work description"]),
        "recommended_date": df["recommended_date"],
        "sanction_date": df["sanction_date"],
        "sanction_amount": df["sanction_amount"],
        "work_status": clean_text(df["Work Status"]),
    })
    return out, n_dropped


def load_all_artifacts():
    with open(ENCODER_PATH, "rb") as f:
        encoders = pickle.load(f)
    anomaly_artifacts = anomaly_detector.load_artifacts()
    delay_clf = delay_model.load_model()
    cost_reg = cost_model.load_model()
    dup_index = duplicate_finder.load_index()
    return {
        "encoders": encoders,
        "anomaly": anomaly_artifacts,
        "delay_model": delay_clf,
        "cost_model": cost_reg,
        "dup_index": dup_index,
    }


def score_uploaded_dataframe(new_sanctioned_df: pd.DataFrame, artifacts: dict = None):
    """
    new_sanctioned_df: output of clean_uploaded_sanctioned() — new works only.
    Returns a DataFrame of scored results for ONLY the new rows.
    """
    if artifacts is None:
        artifacts = load_all_artifacts()

    # 1. Pull historical context from DB
    hist_s, hist_c, hist_a = load_raw_tables(engine)
    hist_s = hist_s.drop(columns=["id"], errors="ignore")

    new_sanctioned_df = new_sanctioned_df.copy()
    new_sanctioned_df["is_new_upload"] = True
    hist_s["is_new_upload"] = False

    combined_s = pd.concat([hist_s, new_sanctioned_df], ignore_index=True)

    # 2. Same merge + derived-feature pipeline as training (new rows have no
    #    completed-work match yet -> is_completed=0, exactly as intended)
    merged = merge_sources(combined_s, hist_c)
    derived = compute_derived_features(merged, hist_a)

    # 3. Encode with the SAVED (not refit) encoders
    encoded, _ = encode_categoricals(derived, encoders=artifacts["encoders"])
    final = finalize_feature_matrix(encoded)

    new_mask = final["is_new_upload"] == True  # noqa: E712
    new_final = final[new_mask].reset_index(drop=True)
    X_new = new_final[FEATURE_COLUMNS].astype(float)

    # 4. Score with each trained model
    anomaly_score, _ = anomaly_detector.score_new(new_final, X_new, artifacts["anomaly"])
    new_final["anomaly_score"] = anomaly_score

    delay_risk_pct = delay_model.score_new(artifacts["delay_model"], X_new)
    new_final["delay_risk_pct"] = delay_risk_pct

    cost_risk_pct, expected_cost = cost_model.score_new(artifacts["cost_model"], new_final, X_new)
    new_final["cost_risk_pct"] = cost_risk_pct
    new_final["expected_cost"] = expected_cost

    dup_results = duplicate_finder.score_duplicates(new_final, artifacts["dup_index"], exclude_self=True)
    new_final["duplicate_score"] = dup_results["duplicate_score"].values
    new_final["duplicate_match_work_id"] = dup_results["duplicate_match_work_id"].values
    new_final["duplicate_confirmed"] = dup_results["duplicate_confirmed"].values

    # 5. Fuse + explain
    new_final["risk_score"] = (
        RISK_WEIGHTS["anomaly"] * new_final["anomaly_score"]
        + RISK_WEIGHTS["delay"] * new_final["delay_risk_pct"]
        + RISK_WEIGHTS["cost"] * new_final["cost_risk_pct"]
        + RISK_WEIGHTS["duplicate"] * new_final["duplicate_score"]
    )
    new_final["risk_band"] = new_final["risk_score"].apply(explain.risk_band)
    new_final["category_median_duration"] = np.nan  # unknown for brand-new works (not yet completed)
    new_final["risk_reasons"] = explain.explain_dataframe(new_final)

    result_cols = [
        "work_id", "state", "work_category", "ida", "ida_missing", "mp_name", "constituency",
        "work_description", "work_status", "sanction_amount", "expected_cost",
        "recommended_date", "sanction_date",
        "anomaly_score", "delay_risk_pct", "cost_risk_pct", "duplicate_score",
        "duplicate_match_work_id", "duplicate_confirmed",
        "risk_score", "risk_band", "risk_reasons",
    ]
    return new_final[result_cols].sort_values("risk_score", ascending=False).reset_index(drop=True)


def score_uploaded_file(file_path: str):
    """Entry point used by routers/upload.py. Reads CSV or Excel, returns
    (scored_df, n_rows_dropped_during_cleaning)."""
    if file_path.lower().endswith((".xlsx", ".xls")):
        raw_df = pd.read_excel(file_path)
    else:
        raw_df = pd.read_csv(file_path)
        # Tolerate the same "title row + header row" shape as the original raw exports
        if "Work" not in _normalize_columns(raw_df).columns:
            raw_df = pd.read_csv(file_path, skiprows=1)

    cleaned, n_dropped = clean_uploaded_sanctioned(raw_df)
    scored = score_uploaded_dataframe(cleaned)
    return scored, n_dropped
