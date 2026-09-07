"""
ml/cost_model.py
──────────────────
Supervised cost-overrun / cost-anomaly prediction — Section B, item 5.

GradientBoostingRegressor learns "given this work's category, state,
agency (IDA), MP, and sanctioned amount, what final amount does a NORMAL
work like this typically get disbursed?" — i.e. a learned, data-driven
expectation, not a fixed budget rule.

Cost_Risk_% is then derived from how far the ACTUAL disbursed amount
deviates from that learned expectation (residual, standardized and
percentile-scaled to 0-100). This can only be computed for COMPLETED
works, since ongoing works have no actual disbursement yet — for those,
Cost_Risk_% is reported as 0 (not yet assessable) until the work
completes; see explain.py for how this is worded to the user so it isn't
mistaken for "confirmed low risk".
"""

import pickle

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score

from config import COST_MODEL_PATH

COST_FEATURE_COLUMNS = [
    "sanction_amount",
    "category_amount_zscore",
    "mp_total_sanctioned",
    "mp_work_count",
    "mp_avg_work_amount",
    "pct_of_mp_allocation",
    "state_enc",
    "work_category_enc",
    "ida_enc",
    "mp_name_enc",
    "constituency_enc",
]

RANDOM_STATE = 42


def _percentile_scale(raw_scores: np.ndarray) -> np.ndarray:
    ranks = pd.Series(raw_scores).rank(pct=True)
    return (ranks * 100).values


def train_cost_model(df: pd.DataFrame, X_full: pd.DataFrame):
    """
    Trains on completed works only (target = actual amount_disbursed).
    Returns: model, metrics, cost_risk_pct for ALL rows (0 for ongoing works).
    """
    # is_completed AND amount_disbursed actually present (~80 completed rows have it
    # missing in the source data — kept in the DB per Phase 1's "don't drop" rule for
    # missing disbursement, but they can't be used as a regression TARGET here)
    completed_mask = (df["is_completed"] == 1) & df["amount_disbursed"].notna()
    X_train_full = X_full.loc[completed_mask, COST_FEATURE_COLUMNS]
    y = df.loc[completed_mask, "amount_disbursed"]

    X_train, X_test, y_train, y_test = train_test_split(
        X_train_full, y, test_size=0.2, random_state=RANDOM_STATE
    )

    model = GradientBoostingRegressor(
        n_estimators=250,
        max_depth=4,
        learning_rate=0.05,
        random_state=RANDOM_STATE,
    )
    model.fit(X_train, y_train)

    y_pred_test = model.predict(X_test)
    metrics = {
        "mae": float(mean_absolute_error(y_test, y_pred_test)),
        "r2": float(r2_score(y_test, y_pred_test)),
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
    }

    # Cost_Risk_% for completed works: how far actual deviates from the learned expectation
    predicted_all_completed = model.predict(X_full.loc[completed_mask, COST_FEATURE_COLUMNS])
    actual_all_completed = df.loc[completed_mask, "amount_disbursed"].values
    residual_pct = np.abs(actual_all_completed - predicted_all_completed) / np.maximum(predicted_all_completed, 1)
    cost_risk_completed = _percentile_scale(residual_pct)

    cost_risk_pct = np.zeros(len(df))
    cost_risk_pct[completed_mask.values] = cost_risk_completed
    # ongoing works: stays 0 ("not yet assessable" — see explain.py wording)

    expected_cost = np.full(len(df), np.nan)
    expected_cost[completed_mask.values] = predicted_all_completed
    # Also compute an expectation for ONGOING works (useful to show "budget check" even pre-completion)
    ongoing_mask = ~completed_mask
    if ongoing_mask.any():
        expected_cost[ongoing_mask.values] = model.predict(X_full.loc[ongoing_mask, COST_FEATURE_COLUMNS])

    return model, metrics, cost_risk_pct, expected_cost, (X_test, y_test, y_pred_test)


def save_model(model):
    with open(COST_MODEL_PATH, "wb") as f:
        pickle.dump(model, f)


def load_model():
    with open(COST_MODEL_PATH, "rb") as f:
        return pickle.load(f)


def score_new(model, df: pd.DataFrame, X_full: pd.DataFrame):
    """Score new/uploaded rows. Only completed rows in the new batch get a
    non-zero Cost_Risk_%; expected_cost is returned for every row."""
    expected_cost = model.predict(X_full[COST_FEATURE_COLUMNS])

    completed_mask = (df["is_completed"] == 1).values
    cost_risk_pct = np.zeros(len(df))
    if completed_mask.any():
        actual = df.loc[completed_mask, "amount_disbursed"].values
        predicted = expected_cost[completed_mask]
        residual_pct = np.abs(actual - predicted) / np.maximum(predicted, 1)
        cost_risk_pct[completed_mask] = _percentile_scale(residual_pct)

    return cost_risk_pct, expected_cost
