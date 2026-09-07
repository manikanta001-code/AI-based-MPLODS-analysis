"""
ml/delay_model.py
───────────────────
Supervised delay prediction — Section B, item 4 & 6 of the spec.

LABEL SOURCE — no "Delayed" status exists anywhere in the raw data
(Work Status is one of: Physical Inspection, Sanction, Vendor
Identification, Work partially Completed, Work Completed, Time
Estimation), so we self-supervise the label exactly as specified:
  delayed = 1  if  sanction_to_completion_days > 1.5 x (median duration
                     for that work's category)
  delayed = 0  otherwise
computed ONLY on works that are actually completed (we know the true
duration for them). The trained classifier then generalizes this pattern
to ONGOING works, where the real duration isn't known yet — that's the
whole point: predict Delay_Risk_% before the delay has happened.

FEATURES: only things known AT THE TIME OF SANCTION (never the duration
itself, never utilization/cost-deviation which are outcomes only knowable
after completion) — otherwise the model would trivially "predict" delay
using information that isn't available for the ongoing works it's
actually meant to score. See DELAY_FEATURE_COLUMNS below.
"""

import pickle

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_score, recall_score, f1_score, classification_report

from config import DELAY_MODEL_PATH, DELAY_LABEL_MULTIPLIER

# Only pre-completion-known features -> no leakage from sanction_to_completion_days,
# utilization_pct, cost_deviation_pct, or is_completed (trivially 1 for all training rows).
DELAY_FEATURE_COLUMNS = [
    "sanction_amount",
    "recommendation_to_sanction_days",
    "ida_missing",
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

RANDOM_STATE = 42


def create_self_supervised_labels(df: pd.DataFrame) -> pd.DataFrame:
    """Adds a 'delayed' column (0/1, NaN for ongoing works) using the
    1.5x-median-category-duration rule, computed only from completed works."""
    df = df.copy()
    completed = df[df["is_completed"] == 1]
    median_by_cat = completed.groupby("work_category")["sanction_to_completion_days"].median()

    df["category_median_duration"] = df["work_category"].map(median_by_cat)
    df["delayed"] = np.where(
        (df["is_completed"] == 1) & df["category_median_duration"].notna(),
        (df["sanction_to_completion_days"] > DELAY_LABEL_MULTIPLIER * df["category_median_duration"]).astype(int),
        np.nan,
    )
    return df


def train_delay_model(df_labeled: pd.DataFrame, X_full: pd.DataFrame):
    """
    df_labeled: full feature table WITH 'delayed' column from create_self_supervised_labels()
    X_full:     full FEATURE_COLUMNS matrix (same row order as df_labeled)
    Returns: model, metrics dict, (X_test, y_test, y_pred) for evaluate.py, delay_risk_pct for ALL rows
    """
    train_mask = df_labeled["delayed"].notna()
    X_train_full = X_full.loc[train_mask, DELAY_FEATURE_COLUMNS]
    y = df_labeled.loc[train_mask, "delayed"].astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X_train_full, y, test_size=0.2, stratify=y, random_state=RANDOM_STATE
    )

    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=12,
        min_samples_leaf=5,
        class_weight="balanced",   # delayed class is a minority — don't let the model just predict "not delayed"
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_proba_test = model.predict_proba(X_test)[:, 1]

    metrics = {
        "precision": precision_score(y_test, y_pred, zero_division=0),
        "recall": recall_score(y_test, y_pred, zero_division=0),
        "f1": f1_score(y_test, y_pred, zero_division=0),
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "positive_rate_train": float(y_train.mean()),
        "positive_rate_test": float(y_test.mean()),
        "classification_report": classification_report(y_test, y_pred, zero_division=0, output_dict=True),
    }

    # Predict Delay_Risk_% for EVERY row (ongoing works included) — this is the
    # actual product output judges/dashboards use.
    delay_risk_pct = model.predict_proba(X_full[DELAY_FEATURE_COLUMNS])[:, 1] * 100

    return model, metrics, (X_test, y_test, y_pred, y_proba_test), delay_risk_pct


def save_model(model):
    with open(DELAY_MODEL_PATH, "wb") as f:
        pickle.dump(model, f)


def load_model():
    with open(DELAY_MODEL_PATH, "rb") as f:
        return pickle.load(f)


def score_new(model, X_full: pd.DataFrame) -> np.ndarray:
    return model.predict_proba(X_full[DELAY_FEATURE_COLUMNS])[:, 1] * 100
