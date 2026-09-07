"""
etl/feature_engine.py
──────────────────────
Builds the ML-ready feature table from the 3 staging tables loaded by
preprocess.py. This is the ONE place feature logic lives — train.py calls
it with fit=True (fits & saves encoders/category-stats), scorer.py calls
it with fit=False on newly-uploaded data (reuses the saved encoders/stats
so scoring is apples-to-apples with what the models were trained on).

WHY THE JOIN HAPPENS HERE AND NOT IN preprocess.py
  Only 58.9% of Sanctioned works have a matching Completed record (see
  database.py docstring). We LEFT-join Completed onto Sanctioned — every
  sanctioned work gets a row; matched ones get real completion_date /
  amount_disbursed, unmatched ones are simply "ongoing" (is_completed=0).
  This also means we naturally get to check "completion before sanction"
  here (in real data: 0 such rows, but code path is real and used if any
  future data has that error — flagged as red-flag, NOT silently dropped:
  a work completed before it was even sanctioned is itself an anomaly
  signal worth showing to an investigator, not something to hide by
  deleting the row).

DERIVED FEATURES (this is where domain knowledge turns raw columns into
signal for the ML models in ml/):
  - recommendation_to_sanction_days : administrative delay before sanction
  - sanction_to_completion_days     : execution duration (NaN if ongoing)
  - is_completed                    : 0/1
  - completed_before_sanctioned     : red-flag bool (should be 0 rows, but checked)
  - utilization_pct                 : amount_disbursed / sanction_amount * 100
  - cost_deviation_pct              : (amount_disbursed - sanction_amount) / sanction_amount * 100
  - category_amount_zscore          : how many std-devs this work's sanction_amount
                                       is from the mean for its Work Category
                                       (this is literally the "3.2σ above category
                                       mean" style explanation the spec asks for)
  - mp_total_sanctioned / mp_work_count / mp_avg_work_amount : per-MP aggregates
  - pct_of_mp_allocation            : this work's amount as % of the MP's total
                                       allocated MPLADS limit (large single works
                                       relative to a small MP allocation are a
                                       natural red flag)

CATEGORICAL ENCODING
  state / work_category / ida / work_status / mp_name / constituency are
  label-encoded. During scoring (fit=False) any category unseen at training
  time is mapped to a reserved "UNSEEN" code rather than crashing — this is
  exactly what happens for genuinely new agencies/MPs appearing in an
  uploaded file.
"""

import os
import sys

import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # backend/
from config import DATABASE_URL

# Final numeric feature columns fed into the ML models (order matters — must
# match exactly between training and scoring).
FEATURE_COLUMNS = [
    "sanction_amount",
    "recommendation_to_sanction_days",
    "sanction_to_completion_days",   # NaN-filled with -1 sentinel for ongoing works
    "is_completed",
    "ida_missing",
    "amount_missing",
    "utilization_pct",               # NaN-filled with -1 sentinel for ongoing works
    "category_amount_zscore",
    "mp_total_sanctioned",
    "mp_work_count",
    "mp_avg_work_amount",
    "pct_of_mp_allocation",
    "state_enc",
    "work_category_enc",
    "ida_enc",
    "work_status_enc",
    "mp_name_enc",
    "constituency_enc",
]

CATEGORICAL_COLUMNS = ["state", "work_category", "ida", "work_status", "mp_name", "constituency"]
UNSEEN_CODE = -1  # reserved label for categories not present at training time


def load_raw_tables(engine=None):
    """Load the 3 cleaned staging tables produced by preprocess.py."""
    import sqlalchemy
    if engine is None:
        engine = sqlalchemy.create_engine(DATABASE_URL)
    df_s = pd.read_sql("SELECT * FROM works_sanctioned", engine, parse_dates=["recommended_date", "sanction_date"])
    df_c = pd.read_sql("SELECT * FROM works_completed", engine, parse_dates=["completion_date"])
    df_a = pd.read_sql("SELECT * FROM mp_allocations", engine)
    return df_s, df_c, df_a


def merge_sources(df_s: pd.DataFrame, df_c: pd.DataFrame) -> pd.DataFrame:
    """Left-join Completed onto Sanctioned by work_id. One row per sanctioned work."""
    completed_cols = df_c[["work_id", "completion_date", "amount_disbursed", "amount_missing"]].copy()
    # A work_id could in theory appear twice in Completed (re-reported); keep the latest.
    completed_cols = completed_cols.sort_values("completion_date").drop_duplicates("work_id", keep="last")

    merged = df_s.merge(completed_cols, on="work_id", how="left", suffixes=("", "_completed"))
    merged["amount_missing"] = merged["amount_missing"].fillna(False)
    return merged


def compute_derived_features(merged: pd.DataFrame, df_a: pd.DataFrame) -> pd.DataFrame:
    df = merged.copy()

    df["is_completed"] = df["completion_date"].notna().astype(int)

    df["recommendation_to_sanction_days"] = (df["sanction_date"] - df["recommended_date"]).dt.days
    df["sanction_to_completion_days"] = (df["completion_date"] - df["sanction_date"]).dt.days

    # Red flag, not a drop: a work "completed" before it was sanctioned.
    df["completed_before_sanctioned"] = (
        df["sanction_to_completion_days"].notna() & (df["sanction_to_completion_days"] < 0)
    ).astype(int)

    df["utilization_pct"] = np.where(
        df["is_completed"] == 1,
        (df["amount_disbursed"] / df["sanction_amount"]) * 100,
        np.nan,
    )
    df["cost_deviation_pct"] = np.where(
        df["is_completed"] == 1,
        ((df["amount_disbursed"] - df["sanction_amount"]) / df["sanction_amount"]) * 100,
        np.nan,
    )

    # Category-level statistical outlier signal (feeds explain.py's "Xσ above category mean")
    cat_stats = df.groupby("work_category")["sanction_amount"].agg(["mean", "std"]).rename(
        columns={"mean": "cat_mean", "std": "cat_std"}
    )
    cat_stats["cat_std"] = cat_stats["cat_std"].replace(0, np.nan)  # avoid div-by-zero
    df = df.merge(cat_stats, left_on="work_category", right_index=True, how="left")
    df["category_amount_zscore"] = (df["sanction_amount"] - df["cat_mean"]) / df["cat_std"]
    df["category_amount_zscore"] = df["category_amount_zscore"].fillna(0)

    # Per-MP aggregates
    mp_stats = df.groupby("mp_name")["sanction_amount"].agg(
        mp_total_sanctioned="sum", mp_work_count="count", mp_avg_work_amount="mean"
    )
    df = df.merge(mp_stats, left_on="mp_name", right_index=True, how="left")

    # % of that MP's total allocated MPLADS limit represented by THIS single work
    alloc = df_a.groupby("mp_name")["allocated_amount"].sum()
    df = df.merge(alloc.rename("mp_allocated_amount"), left_on="mp_name", right_index=True, how="left")
    df["pct_of_mp_allocation"] = np.where(
        df["mp_allocated_amount"].notna() & (df["mp_allocated_amount"] > 0),
        (df["sanction_amount"] / df["mp_allocated_amount"]) * 100,
        np.nan,
    )
    df["pct_of_mp_allocation"] = df["pct_of_mp_allocation"].fillna(df["pct_of_mp_allocation"].median())

    return df


def encode_categoricals(df: pd.DataFrame, encoders: dict = None):
    """
    fit mode (encoders=None): fit a LabelEncoder per categorical column, return (df, encoders)
    score mode (encoders given): reuse them; any unseen category -> UNSEEN_CODE
    """
    df = df.copy()
    fitted = encoders is not None
    out_encoders = {} if not fitted else encoders

    for col in CATEGORICAL_COLUMNS:
        values = df[col].fillna("Unknown").astype(str)
        if not fitted:
            le = LabelEncoder()
            le.fit(values)
            out_encoders[col] = le
        else:
            le = out_encoders[col]

        known = set(le.classes_)
        mapped = values.where(values.isin(known), other=None)
        codes = np.full(len(values), UNSEEN_CODE, dtype=int)
        mask = mapped.notna()
        if mask.any():
            codes[mask.values] = le.transform(mapped[mask])
        df[f"{col}_enc"] = codes

    return df, out_encoders


def finalize_feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Sentinel-fill the two NaN-when-ongoing columns, select FEATURE_COLUMNS in fixed order."""
    df = df.copy()
    df["sanction_to_completion_days"] = df["sanction_to_completion_days"].fillna(-1)
    df["utilization_pct"] = df["utilization_pct"].fillna(-1)
    df["ida_missing"] = df["ida_missing"].astype(int)
    df["amount_missing"] = df["amount_missing"].astype(int)
    return df


def build_feature_table(engine=None, fit: bool = True, encoders: dict = None):
    """
    Top-level entry point.
      fit=True  (training):  loads all 3 staging tables, fits encoders, returns
                              (full_df, X[FEATURE_COLUMNS], encoders)
      fit=False (scoring):   caller passes in already-cleaned new sanctioned/
                              completed/allocation dataframes via `engine=None`
                              and monkeypatches load_raw_tables — in practice
                              scorer.py calls the lower-level functions directly
                              (merge_sources -> compute_derived_features ->
                              encode_categoricals(..., encoders=saved_encoders)
                              -> finalize_feature_matrix) so it can feed in
                              newly uploaded data instead of the DB tables.
    """
    df_s, df_c, df_a = load_raw_tables(engine)
    merged = merge_sources(df_s, df_c)
    derived = compute_derived_features(merged, df_a)
    encoded, out_encoders = encode_categoricals(derived, encoders=encoders if not fit else None)
    final = finalize_feature_matrix(encoded)
    X = final[FEATURE_COLUMNS].astype(float)
    return final, X, out_encoders


if __name__ == "__main__":
    full_df, X, encoders = build_feature_table(fit=True)
    print(f"Feature table shape: {full_df.shape}")
    print(f"Feature matrix shape (fed to ML models): {X.shape}")
    print(f"\nColumns in X:\n{list(X.columns)}")
    print(f"\nSample rows:\n{X.sample(5, random_state=42).to_string()}")
    print(f"\nis_completed distribution:\n{full_df['is_completed'].value_counts()}")
    print(f"\ncompleted_before_sanctioned flags: {full_df['completed_before_sanctioned'].sum()}")
    print(f"\nNaN check on X:\n{X.isna().sum()[X.isna().sum() > 0]}")
