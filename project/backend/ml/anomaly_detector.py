"""
ml/anomaly_detector.py
────────────────────────
Unsupervised anomaly detection — Section A of the spec. No fixed
thresholds: every score below is LEARNED from the data's own distribution
(percentile-rank scaled 0-100), not a hand-picked cutoff.

Three independent detectors, fused by averaging their 0-100 scores:
  1. IsolationForest   — isolates points that split away from the crowd
                          in few random partitions (good at multivariate
                          outliers across the whole feature space).
  2. LocalOutlierFactor (novelty=True) — measures local density deviation
                          (catches outliers relative to their *neighbourhood*,
                          which IsolationForest can miss when anomalies
                          cluster together, e.g. a batch of works from the
                          same suspicious agency).
  3. PCA reconstruction error, fit PER WORK CATEGORY — different work
     categories have structurally different "normal" ranges (a school-room
     construction and a flood-embankment project are not comparable in
     scale), so one global PCA would just re-learn "category" as the
     dominant axis of variance. Fitting PCA per category means the error
     reflects "how unusual is this work FOR ITS CATEGORY", not just "is
     this an expensive category".

Why ensemble instead of picking one: each detector has known blind spots
(IF misses local-density anomalies, LOF is sensitive to a badly-chosen k,
PCA misses non-linear structure) — averaging three independent, differently-
biased detectors is more robust than trusting any single one, and is the
standard approach for this kind of ensemble anomaly detection.
"""

import os
import pickle

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from config import IF_CONTAMINATION, ISOLATION_FOREST_PATH, LOF_PATH, SCALER_PATH, MODEL_DIR

PCA_MODEL_PATH = os.path.join(MODEL_DIR, "pca_by_category.pkl")

RANDOM_STATE = 42


def _percentile_scale(raw_scores: np.ndarray) -> np.ndarray:
    """Rank-based scaling to 0-100 AGAINST ITSELF. Only correct when raw_scores
    is the full training distribution — see _percentile_scale_against_reference
    for scoring new/small batches, where self-ranking is wrong (e.g. 300 new
    rows that are ALL extreme would rank themselves 0-100 relative to EACH
    OTHER, hiding how extreme they are vs. the real, trained-on population)."""
    ranks = pd.Series(raw_scores).rank(pct=True)
    return (ranks * 100).values


def _percentile_scale_against_reference(raw_scores: np.ndarray, reference_raw: np.ndarray) -> np.ndarray:
    """Percentile-rank new raw scores against the SAVED TRAINING distribution,
    via binary search (np.searchsorted) into the sorted reference array. This
    is what makes scores comparable between training-time and scoring-time —
    a new row's score means 'more anomalous than X% of the training data',
    not 'more anomalous than X% of whatever batch happened to be uploaded'."""
    sorted_ref = np.sort(reference_raw)
    ranks = np.searchsorted(sorted_ref, raw_scores, side="right")
    return (ranks / len(sorted_ref)) * 100


def fit_isolation_forest(X: pd.DataFrame):
    model = IsolationForest(
        n_estimators=200,
        contamination=IF_CONTAMINATION,
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    model.fit(X)
    # score_samples: higher = more normal, so negate -> higher = more anomalous
    raw = -model.score_samples(X)
    return model, _percentile_scale(raw), raw


def fit_lof(X_scaled: np.ndarray):
    model = LocalOutlierFactor(n_neighbors=35, novelty=True, contamination=IF_CONTAMINATION, n_jobs=-1)
    model.fit(X_scaled)
    raw = -model.decision_function(X_scaled)  # higher = more anomalous
    return model, _percentile_scale(raw), raw


def fit_pca_by_category(df: pd.DataFrame, X: pd.DataFrame, category_col: str = "work_category"):
    """One small PCA model per work category. Returns {category: (pca, scaler)} and
    the 0-100 percentile-scaled reconstruction-error score for every row."""
    pca_models = {}
    recon_error = np.zeros(len(df))
    categories = df[category_col].values

    for cat in df[category_col].unique():
        mask = categories == cat
        n_rows = mask.sum()
        if n_rows < 10:
            # Too few rows in this category for a stable PCA -> fall back to global mean error 0
            pca_models[cat] = None
            continue

        Xc = X[mask]
        scaler = StandardScaler()
        Xc_scaled = scaler.fit_transform(Xc)

        n_components = min(5, Xc_scaled.shape[1], n_rows - 1)
        pca = PCA(n_components=n_components, random_state=RANDOM_STATE)
        transformed = pca.fit_transform(Xc_scaled)
        reconstructed = pca.inverse_transform(transformed)
        err = np.sum((Xc_scaled - reconstructed) ** 2, axis=1)

        recon_error[mask] = err
        pca_models[cat] = (pca, scaler, n_components)

    # Scale reconstruction error to 0-100 WITHIN each category (fair comparison
    # across categories of very different natural error magnitudes)
    recon_score = np.zeros(len(df))
    for cat in df[category_col].unique():
        mask = categories == cat
        if mask.sum() < 10:
            recon_score[mask] = 0  # not enough data to judge — neutral, not zero-confidence flag
        else:
            recon_score[mask] = _percentile_scale(recon_error[mask])

    return pca_models, recon_score, recon_error


def train_anomaly_ensemble(df: pd.DataFrame, X: pd.DataFrame):
    """
    df: full feature table (needs 'work_category' column for PCA grouping)
    X:  numeric feature matrix (FEATURE_COLUMNS from feature_engine.py)
    Returns: anomaly_score (0-100 per row), and the fitted artifacts to save.
    """
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    if_model, if_score, if_raw_train = fit_isolation_forest(X)
    lof_model, lof_score, lof_raw_train = fit_lof(X_scaled)
    pca_models, pca_score, pca_raw_train = fit_pca_by_category(df, X)

    anomaly_score = (if_score + lof_score + pca_score) / 3.0

    # Per-category reference reconstruction-error arrays, needed to percentile-scale
    # NEW rows' PCA error against the right category's training distribution.
    pca_raw_train_by_category = {}
    categories = df["work_category"].values
    for cat in df["work_category"].unique():
        mask = categories == cat
        if mask.sum() >= 10:
            pca_raw_train_by_category[cat] = pca_raw_train[mask]

    artifacts = {
        "isolation_forest": if_model,
        "lof": lof_model,
        "pca_by_category": pca_models,
        "scaler": scaler,
        # reference distributions from the TRAINING data, so new/uploaded rows are
        # percentile-scaled against the population the models were trained on
        "if_raw_train": if_raw_train,
        "lof_raw_train": lof_raw_train,
        "pca_raw_train_by_category": pca_raw_train_by_category,
    }
    component_scores = pd.DataFrame({
        "if_score": if_score,
        "lof_score": lof_score,
        "pca_score": pca_score,
        "anomaly_score": anomaly_score,
    })
    return anomaly_score, component_scores, artifacts


def save_artifacts(artifacts: dict):
    with open(ISOLATION_FOREST_PATH, "wb") as f:
        pickle.dump(artifacts["isolation_forest"], f)
    with open(LOF_PATH, "wb") as f:
        pickle.dump(artifacts["lof"], f)
    with open(PCA_MODEL_PATH, "wb") as f:
        pickle.dump(artifacts["pca_by_category"], f)
    with open(SCALER_PATH, "wb") as f:
        pickle.dump(artifacts["scaler"], f)
    # reference training distributions, needed by score_new for correct percentile scaling
    with open(os.path.join(MODEL_DIR, "anomaly_reference_scores.pkl"), "wb") as f:
        pickle.dump({
            "if_raw_train": artifacts["if_raw_train"],
            "lof_raw_train": artifacts["lof_raw_train"],
            "pca_raw_train_by_category": artifacts["pca_raw_train_by_category"],
        }, f)


def load_artifacts():
    with open(ISOLATION_FOREST_PATH, "rb") as f:
        if_model = pickle.load(f)
    with open(LOF_PATH, "rb") as f:
        lof_model = pickle.load(f)
    with open(PCA_MODEL_PATH, "rb") as f:
        pca_models = pickle.load(f)
    with open(SCALER_PATH, "rb") as f:
        scaler = pickle.load(f)
    with open(os.path.join(MODEL_DIR, "anomaly_reference_scores.pkl"), "rb") as f:
        ref = pickle.load(f)
    return {
        "isolation_forest": if_model, "lof": lof_model, "pca_by_category": pca_models, "scaler": scaler,
        "if_raw_train": ref["if_raw_train"], "lof_raw_train": ref["lof_raw_train"],
        "pca_raw_train_by_category": ref["pca_raw_train_by_category"],
    }


def score_new(df: pd.DataFrame, X: pd.DataFrame, artifacts: dict, category_col: str = "work_category"):
    """Score NEW (e.g. uploaded) rows with already-fitted artifacts, percentile-ranked
    against the TRAINING distribution (not the new batch's own distribution — see
    _percentile_scale_against_reference docstring for why that matters). Used by scorer.py
    and by evaluate.py's synthetic-anomaly test."""
    if_model = artifacts["isolation_forest"]
    lof_model = artifacts["lof"]
    pca_models = artifacts["pca_by_category"]
    scaler = artifacts["scaler"]

    if_raw = -if_model.score_samples(X)
    if_score = _percentile_scale_against_reference(if_raw, artifacts["if_raw_train"])

    X_scaled = scaler.transform(X)
    lof_raw = -lof_model.decision_function(X_scaled)
    lof_score = _percentile_scale_against_reference(lof_raw, artifacts["lof_raw_train"])

    recon_error = np.zeros(len(df))
    pca_score = np.zeros(len(df))
    categories = df[category_col].values
    pca_ref_by_cat = artifacts["pca_raw_train_by_category"]
    for cat in np.unique(categories):
        mask = categories == cat
        entry = pca_models.get(cat)
        if entry is None or cat not in pca_ref_by_cat:
            recon_error[mask] = 0
            pca_score[mask] = 0
            continue
        pca, cat_scaler, n_components = entry
        Xc_scaled = cat_scaler.transform(X[mask])
        transformed = pca.transform(Xc_scaled)
        reconstructed = pca.inverse_transform(transformed)
        err = np.sum((Xc_scaled - reconstructed) ** 2, axis=1)
        recon_error[mask] = err
        pca_score[mask] = _percentile_scale_against_reference(err, pca_ref_by_cat[cat])

    anomaly_score = (if_score + lof_score + pca_score) / 3.0
    return anomaly_score, pd.DataFrame({"if_score": if_score, "lof_score": lof_score, "pca_score": pca_score})
