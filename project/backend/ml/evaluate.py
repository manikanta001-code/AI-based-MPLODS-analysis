"""
ml/evaluate.py
────────────────
Section F of the spec — "judges WILL ask does it work?"

1. Precision/recall/F1 for the delay model on a held-out stratified test
   split (already computed inside delay_model.train_delay_model, just
   surfaced/saved here).
2. Synthetic-anomaly injection test: take real, normal rows and corrupt a
   few features to extreme values that a domain expert would call
   obviously anomalous (10-15x cost blow-up, impossible utilization,
   IDA stripped, etc.), run them back through the TRAINED anomaly
   ensemble, and measure what fraction get flagged High risk. This is a
   live, repeatable "does the anomaly detector actually catch things"
   test for the demo — not a claim about real-world fraud recall, since
   we don't have ground-truth fraud labels (nobody does, for this kind
   of data), but a controlled check on the detector's sensitivity.
3. Feature importance chart (from the delay RandomForest) -> PNG, for the
   presentation deck.
"""

import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from config import METRICS_PATH, FEATURE_IMPORTANCE_PNG, RISK_HIGH_THRESHOLD
from ml.delay_model import DELAY_FEATURE_COLUMNS
from ml import anomaly_detector

RANDOM_STATE = 42


def inject_synthetic_anomalies(X: pd.DataFrame, df: pd.DataFrame, n=300, seed=RANDOM_STATE):
    """
    Samples n normal rows and corrupts them into synthetic, obviously-anomalous
    rows by extreme perturbation of a random subset of features. Returns the
    corrupted (X_synth, df_synth) ready to feed into anomaly_detector.score_new.
    """
    rng = np.random.default_rng(seed)
    sample_idx = rng.choice(len(X), size=min(n, len(X)), replace=False)

    X_synth = X.iloc[sample_idx].copy().reset_index(drop=True)
    df_synth = df.iloc[sample_idx].copy().reset_index(drop=True)

    for i in range(len(X_synth)):
        kind = rng.integers(0, 3)
        if kind == 0:
            # extreme cost blow-up
            X_synth.loc[i, "sanction_amount"] *= rng.uniform(8, 15)
            X_synth.loc[i, "category_amount_zscore"] = rng.uniform(6, 10)
        elif kind == 1:
            # impossible utilization (heavily over-disbursed)
            X_synth.loc[i, "utilization_pct"] = rng.uniform(300, 600)
            df_synth.loc[i, "is_completed"] = 1
        else:
            # IDA stripped + tiny administrative delay masking a large amount
            X_synth.loc[i, "ida_missing"] = 1
            X_synth.loc[i, "sanction_amount"] *= rng.uniform(5, 9)

    return X_synth, df_synth


def run_synthetic_anomaly_test(df: pd.DataFrame, X: pd.DataFrame, artifacts: dict):
    X_synth, df_synth = inject_synthetic_anomalies(X, df)
    synth_scores, _ = anomaly_detector.score_new(df_synth, X_synth, artifacts)
    detected = (synth_scores >= RISK_HIGH_THRESHOLD).sum()
    detection_rate = detected / len(synth_scores)
    return {
        "n_synthetic_anomalies_injected": int(len(synth_scores)),
        "n_detected_as_high_risk": int(detected),
        "detection_rate": float(detection_rate),
        "mean_synthetic_anomaly_score": float(np.mean(synth_scores)),
    }


def plot_feature_importance(delay_model, save_path=FEATURE_IMPORTANCE_PNG):
    importances = delay_model.feature_importances_
    order = np.argsort(importances)[::-1]
    names = [DELAY_FEATURE_COLUMNS[i] for i in order]
    values = importances[order]

    plt.figure(figsize=(9, 6))
    plt.barh(names[::-1], values[::-1], color="#2563eb")
    plt.xlabel("Feature importance")
    plt.title("Delay Model — RandomForest Feature Importance")
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close()
    return save_path


def save_metrics(all_metrics: dict, path=METRICS_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(all_metrics, f, indent=2, default=str)
