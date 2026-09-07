"""
ml/explain.py
───────────────
Section D of the spec: "Rules = explainability only, never detection."

Every number below (anomaly/delay/cost/duplicate scores) was produced by
a trained ML model in anomaly_detector.py / delay_model.py / cost_model.py
/ duplicate_finder.py. This module does NOT detect anything — it only
translates already-computed ML outputs + the underlying feature values
into a plain-English sentence a non-technical MP, district officer, or
judge can read, e.g.:

    "Anomaly score 92 BECAUSE cost is 3.2σ above category mean AND
     utilization 145% (disbursed > sanctioned)"

If this module were deleted entirely, every risk score and High/Medium/Low
classification would be IDENTICAL — only the human-readable reasons would
be gone. That's the "rules never drive detection" guarantee.
"""

import pandas as pd

from config import RISK_HIGH_THRESHOLD, RISK_MEDIUM_THRESHOLD


def risk_band(score: float) -> str:
    if score >= RISK_HIGH_THRESHOLD:
        return "High"
    if score >= RISK_MEDIUM_THRESHOLD:
        return "Medium"
    return "Low"


def explain_row(row: pd.Series) -> list:
    """row must contain: anomaly_score, delay_risk_pct, cost_risk_pct, duplicate_score,
    category_amount_zscore, utilization_pct, ida_missing, pct_of_mp_allocation,
    is_completed, completed_before_sanctioned, duplicate_confirmed, duplicate_match_work_id,
    work_status, sanction_to_completion_days, category_median_duration (optional)."""
    reasons = []

    # --- Anomaly ---
    if row.get("anomaly_score", 0) >= RISK_HIGH_THRESHOLD:
        sub_reasons = []
        z = row.get("category_amount_zscore", 0)
        if abs(z) >= 2:
            direction = "above" if z > 0 else "below"
            sub_reasons.append(f"sanction amount is {abs(z):.1f}σ {direction} its category's average")
        util = row.get("utilization_pct", -1)
        if util >= 120:
            sub_reasons.append(f"utilization is {util:.0f}% (disbursed exceeds sanctioned amount)")
        elif 0 <= util < 40 and row.get("is_completed") == 1:
            sub_reasons.append(f"utilization is only {util:.0f}% despite being marked completed")
        if row.get("ida_missing"):
            sub_reasons.append("no Implementing/Developmental Agency (IDA) on record")
        if row.get("completed_before_sanctioned"):
            sub_reasons.append("completion date is recorded BEFORE the sanction date")
        if row.get("pct_of_mp_allocation", 0) >= 5:
            sub_reasons.append(f"this single work is {row['pct_of_mp_allocation']:.1f}% of the MP's total allocated limit")

        if sub_reasons:
            reasons.append(f"Anomaly score {row['anomaly_score']:.0f} because " + " AND ".join(sub_reasons))
        else:
            reasons.append(f"Anomaly score {row['anomaly_score']:.0f} — unusual combination of features "
                            f"relative to similar works (no single dominant factor)")

    # --- Delay ---
    delay_risk = row.get("delay_risk_pct", 0)
    if delay_risk >= RISK_HIGH_THRESHOLD:
        if row.get("is_completed") == 1:
            dur = row.get("sanction_to_completion_days")
            med = row.get("category_median_duration")
            if pd.notna(dur) and pd.notna(med) and med > 0:
                reasons.append(
                    f"Delay risk {delay_risk:.0f}% — actually took {dur:.0f} days vs. category median "
                    f"of {med:.0f} days ({dur/med:.1f}x)"
                )
            else:
                reasons.append(f"Delay risk {delay_risk:.0f}% based on learned delay patterns for similar works")
        else:
            reasons.append(
                f"Delay risk {delay_risk:.0f}% (ongoing, status: {row.get('work_status', 'Unknown')}) — "
                f"pattern matches historically-delayed works of this category/agency/MP"
            )

    # --- Cost ---
    cost_risk = row.get("cost_risk_pct", 0)
    if cost_risk >= RISK_HIGH_THRESHOLD and row.get("is_completed") == 1:
        reasons.append(
            f"Cost risk {cost_risk:.0f}% — disbursed amount deviates significantly from the "
            f"ML-predicted expected cost for this category/state/agency combination"
        )
    elif row.get("is_completed") == 0:
        pass  # cost risk not yet assessable for ongoing works — deliberately silent, see cost_model.py

    # --- Duplicate ---
    if row.get("duplicate_confirmed"):
        reasons.append(
            f"Possible duplicate work — {row.get('duplicate_score', 0):.0f}% text-similarity match "
            f"to Work ID {row.get('duplicate_match_work_id')}, confirmed by fuzzy-text check"
        )

    if not reasons:
        reasons.append("No significant risk factors detected")

    return reasons


def explain_dataframe(df: pd.DataFrame) -> pd.Series:
    """Vectorized-ish wrapper: returns a Series of '; '.join(reasons) per row."""
    return df.apply(lambda row: "; ".join(explain_row(row)), axis=1)
