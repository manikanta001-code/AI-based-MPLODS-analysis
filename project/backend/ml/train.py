"""
ml/train.py
─────────────
Runs the full Phase 2 pipeline end-to-end:
  1. Build the feature table (etl/feature_engine.py)
  2. Self-supervised delay labels
  3. Train: delay model, cost model, anomaly ensemble, duplicate index
  4. Fuse into Risk_Score (Section E) + High/Medium/Low band
  5. Generate plain-English reasons (ml/explain.py)
  6. Evaluate (ml/evaluate.py): precision/recall/F1, synthetic-anomaly
     detection rate, feature-importance chart
  7. Save every model artifact as .pkl + metrics.json
  8. Save the full scored table into SQLite (table: work_risk_scores) so
     the FastAPI routers in Phase 3 can just query it directly
  9. Print a sample of flagged high-risk works with their reasons

Run from backend/:
    python ml/train.py
"""

import os
import pickle
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # backend/
from config import (
    RISK_WEIGHTS, ENCODER_PATH, DATABASE_URL, MODEL_DIR,
)
from database import engine
from etl.feature_engine import build_feature_table
from ml import anomaly_detector, delay_model, cost_model, duplicate_finder, explain, evaluate


def fuse_risk_score(df: pd.DataFrame) -> pd.Series:
    """Section E: Risk_Score = 0.35*Anomaly + 0.30*Delay + 0.20*Cost + 0.15*Duplicate"""
    return (
        RISK_WEIGHTS["anomaly"] * df["anomaly_score"]
        + RISK_WEIGHTS["delay"] * df["delay_risk_pct"]
        + RISK_WEIGHTS["cost"] * df["cost_risk_pct"]
        + RISK_WEIGHTS["duplicate"] * df["duplicate_score"]
    )


def main():
    t0 = time.time()
    print("=" * 70)
    print("PHASE 2 — ML TRAINING PIPELINE")
    print("=" * 70)

    # ── 1. Features ──────────────────────────────────────────────────
    print("\n[1/7] Building feature table ...")
    full_df, X, encoders = build_feature_table(fit=True)
    print(f"      {full_df.shape[0]} works, {X.shape[1]} numeric features")

    with open(ENCODER_PATH, "wb") as f:
        pickle.dump(encoders, f)

    # ── 2. Self-supervised delay labels ─────────────────────────────
    print("\n[2/7] Creating self-supervised delay labels (>1.5x category median duration) ...")
    full_df = delay_model.create_self_supervised_labels(full_df)
    n_labeled = full_df["delayed"].notna().sum()
    n_delayed = full_df["delayed"].sum()
    print(f"      {n_labeled} completed works labeled; {int(n_delayed)} ({n_delayed/n_labeled:.1%}) flagged 'delayed'")

    # ── 3a. Delay model ─────────────────────────────────────────────
    print("\n[3/7] Training delay model (RandomForestClassifier) ...")
    delay_clf, delay_metrics, delay_test_data, delay_risk_pct = delay_model.train_delay_model(full_df, X)
    full_df["delay_risk_pct"] = delay_risk_pct
    print(f"      precision={delay_metrics['precision']:.3f}  recall={delay_metrics['recall']:.3f}  "
          f"f1={delay_metrics['f1']:.3f}  (test set n={delay_metrics['test_rows']})")
    delay_model.save_model(delay_clf)

    # ── 3b. Cost model ──────────────────────────────────────────────
    print("\n[4/7] Training cost model (GradientBoostingRegressor) ...")
    cost_reg, cost_metrics, cost_risk_pct, expected_cost, cost_test_data = cost_model.train_cost_model(full_df, X)
    full_df["cost_risk_pct"] = cost_risk_pct
    full_df["expected_cost"] = expected_cost
    print(f"      MAE=₹{cost_metrics['mae']:,.0f}  R²={cost_metrics['r2']:.3f}  (test set n={cost_metrics['test_rows']})")
    cost_model.save_model(cost_reg)

    # ── 3c. Anomaly ensemble ────────────────────────────────────────
    print("\n[5/7] Training anomaly ensemble (IsolationForest + LOF + per-category PCA) ...")
    anomaly_score, anomaly_components, anomaly_artifacts = anomaly_detector.train_anomaly_ensemble(full_df, X)
    full_df["anomaly_score"] = anomaly_score
    for col in ["if_score", "lof_score", "pca_score"]:
        full_df[col] = anomaly_components[col].values
    print(f"      mean anomaly score={anomaly_score.mean():.1f}  "
          f"High-risk (>=70) count={(anomaly_score>=70).sum()}")
    anomaly_detector.save_artifacts(anomaly_artifacts)

    # ── 3d. Duplicate finder ────────────────────────────────────────
    print("\n[6/7] Building TF-IDF duplicate index (blocked by state + category) ...")
    dup_index = duplicate_finder.build_duplicate_index(full_df)
    dup_results = duplicate_finder.score_duplicates(full_df, dup_index)
    full_df["duplicate_score"] = dup_results["duplicate_score"].values
    full_df["duplicate_match_work_id"] = dup_results["duplicate_match_work_id"].values
    full_df["duplicate_confirmed"] = dup_results["duplicate_confirmed"].values
    print(f"      {len(dup_index)} (state, category) blocks indexed; "
          f"{int(full_df['duplicate_confirmed'].sum())} confirmed near-duplicate pairs found")
    duplicate_finder.save_index(dup_index)

    # ── 4. Fuse risk score ──────────────────────────────────────────
    full_df["risk_score"] = fuse_risk_score(full_df)
    full_df["risk_band"] = full_df["risk_score"].apply(explain.risk_band)
    print(f"\nRisk band distribution:\n{full_df['risk_band'].value_counts()}")

    # ── 5. Explanations ─────────────────────────────────────────────
    print("\nGenerating plain-English explanations ...")
    full_df["risk_reasons"] = explain.explain_dataframe(full_df)

    # ── 6. Evaluation ────────────────────────────────────────────────
    print("\n[7/7] Evaluating ...")
    synthetic_results = evaluate.run_synthetic_anomaly_test(full_df, X, anomaly_artifacts)
    print(f"      Synthetic anomaly injection: {synthetic_results['n_detected_as_high_risk']}/"
          f"{synthetic_results['n_synthetic_anomalies_injected']} detected as High risk "
          f"({synthetic_results['detection_rate']:.1%})")

    png_path = evaluate.plot_feature_importance(delay_clf)
    print(f"      Feature importance chart saved -> {png_path}")

    all_metrics = {
        "delay_model": {k: v for k, v in delay_metrics.items() if k != "classification_report"},
        "delay_model_classification_report": delay_metrics["classification_report"],
        "cost_model": cost_metrics,
        "synthetic_anomaly_test": synthetic_results,
        "risk_band_distribution": full_df["risk_band"].value_counts().to_dict(),
        "n_works_total": int(len(full_df)),
        "n_duplicate_confirmed": int(full_df["duplicate_confirmed"].sum()),
    }
    evaluate.save_metrics(all_metrics)
    print(f"      metrics.json saved")

    # ── 7. Persist scored table to SQLite for Phase 3 API ───────────
    score_cols = [
        "work_id", "state", "work_category", "ida", "ida_missing", "mp_name", "constituency",
        "work_description", "work_status", "sanction_amount", "amount_disbursed", "expected_cost",
        "is_completed", "completed_before_sanctioned", "recommended_date", "sanction_date", "completion_date",
        "sanction_to_completion_days", "utilization_pct",
        "anomaly_score", "if_score", "lof_score", "pca_score",
        "delay_risk_pct", "cost_risk_pct", "duplicate_score", "duplicate_match_work_id", "duplicate_confirmed",
        "risk_score", "risk_band", "risk_reasons",
    ]
    scored_table = full_df[score_cols].copy()
    for c in ["recommended_date", "sanction_date", "completion_date"]:
        scored_table[c] = scored_table[c].astype(str)
    scored_table.to_sql("work_risk_scores", engine, if_exists="replace", index=False)
    print(f"\nSaved {len(scored_table)} scored works -> SQLite table 'work_risk_scores'")

    # ── 8. Sample flagged output ─────────────────────────────────────
    print("\n" + "=" * 70)
    print("SAMPLE HIGH-RISK FLAGGED WORKS")
    print("=" * 70)
    top = full_df.sort_values("risk_score", ascending=False).head(5)
    for _, row in top.iterrows():
        print(f"\nWork ID {row['work_id']}  |  {row['state']}  |  {row['work_category']}  |  "
              f"Risk Score: {row['risk_score']:.1f} ({row['risk_band']})")
        print(f"  MP: {row['mp_name']}  |  Sanction Amount: ₹{row['sanction_amount']:,.0f}")
        print(f"  Reasons: {row['risk_reasons']}")

    print(f"\nTotal pipeline time: {time.time()-t0:.1f}s")
    print(f"\nArtifacts saved in: {MODEL_DIR}")


if __name__ == "__main__":
    main()
