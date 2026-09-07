"""
etl/preprocess.py
──────────────────
Reads the 3 raw MPLADS files -> cleans -> loads into SQLite.

Run from the backend/ directory:
    python etl/preprocess.py

WHAT THIS DOES, PER FILE
-------------------------------------------------------------------------
1. Drop the trailing "Grand Total" summary row (all 3 raw files end with
   one — it is not a real record and its numeric total would corrupt any
   aggregate stat if left in).
2. Extract a clean `work_id` from the free-text "Work" column. Raw format
   is:  WS/ MP<n>/<year>-<year>/<digits>-<category description...>
   The trailing description can itself contain "/" characters (e.g.
   "flood control embankments/ protection walls"), so a naive
   `split('/')[-1]` breaks. We anchor a regex to the fixed-format PREFIX
   instead: ^WS/\\s*MP\\d+/\\d{4}-\\d{4}/(\\d+)-
3. Parse all date columns with the exact source format (%d-%b-%Y, e.g.
   "08-Jul-2024"); anything that fails to parse becomes NaT rather than
   crashing the load.
4. Clean amount columns: strip "₹" and thousands-commas, coerce to float.
5. Missing-value handling (per spec, applied per column meaning):
     - IDA blank            -> fill "Unknown" AND set ida_missing=True
                                (this is a genuine red flag: no
                                Implementing/Developmental Agency on
                                record for a sanctioned/completed work)
     - Completion Date blank-> LEFT AS NULL, never dropped (work is
                                simply still in progress; the ML layer in
                                Phase 2 reads this as "ongoing")
     - Amount Disbursed blank -> LEFT AS NULL, flagged amount_missing=True
     - Sanction Amount blank -> ROW DROPPED (can't assess fund
                                utilization/risk for a work with no
                                sanctioned amount on record)
6. Data-ERROR removal (NOT outlier removal — outliers are exactly what
   the anomaly detector in Phase 2 is meant to catch, so we keep them):
     - Sanction Amount <= 0 dropped (impossible value, not a real
       small-but-legitimate work)
     - Amount Disbursed <= 0 dropped from Completed file for the same
       reason
   (No sanction_date vs completion_date "completion before sanction"
   check happens here because these live in two different staging
   tables in this schema — see database.py docstring for why — that
   check is performed in Phase 2's feature_engine.py once the two are
   joined per Work ID.)
"""

import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # backend/
from config import SANCTIONED_CSV, COMPLETED_CSV, ALLOCATION_CSV, RAW_DATE_FORMAT
from database import init_db, engine, SessionLocal, WorkSanctioned, WorkCompleted, MPAllocation

# Matches: "WS/ MP577/2025-2026/133605-" (whitespace after first slash optional)
WORK_ID_PATTERN = re.compile(r"^WS/\s*MP\d+/\d{4}-\d{4}/(\d+)-")


def extract_work_id(work_text):
    if pd.isna(work_text):
        return None
    m = WORK_ID_PATTERN.match(work_text.strip())
    return m.group(1) if m else None


def clean_amount(series):
    """Strip ₹ symbol and thousands separators, coerce to float."""
    return pd.to_numeric(
        series.astype(str).str.replace("₹", "", regex=False).str.replace(",", "", regex=False).str.strip(),
        errors="coerce",
    )


def clean_text(series):
    return series.astype(str).str.strip().replace({"nan": None, "N/A": None, "": None})


def load_sanctioned():
    print(f"\n[Sanctioned] reading {SANCTIONED_CSV}")
    df = pd.read_csv(SANCTIONED_CSV, skiprows=1)
    before = len(df)

    df = df[df["Sr. No."] != "Grand Total"].copy()

    df["work_id"] = df["Work"].apply(extract_work_id)
    df["sanction_amount"] = clean_amount(df["Sanction Amount ( ₹ )"])
    df["recommended_date"] = pd.to_datetime(df["Recommended date"], format=RAW_DATE_FORMAT, errors="coerce")
    df["sanction_date"] = pd.to_datetime(df["Sanction Date"], format=RAW_DATE_FORMAT, errors="coerce")

    df["ida_missing"] = df["IDA"].isna() | (df["IDA"].astype(str).str.strip() == "")
    df["IDA"] = df["IDA"].fillna("Unknown")
    df.loc[df["IDA"].astype(str).str.strip() == "", "IDA"] = "Unknown"

    # Drop: missing Work ID (couldn't parse), missing/invalid Sanction Amount
    df = df.dropna(subset=["work_id", "sanction_amount"])
    n_dropped_bad_amount = before - len(df)  # includes the Grand Total row + any true parse failures

    # Data-error removal: non-positive sanction amounts (keep large outliers!)
    n_before_error_check = len(df)
    df = df[df["sanction_amount"] > 0]
    n_dropped_nonpositive = n_before_error_check - len(df)

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
        "recommended_date": df["recommended_date"].dt.date,
        "sanction_date": df["sanction_date"].dt.date,
        "sanction_amount": df["sanction_amount"],
        "work_status": clean_text(df["Work Status"]),
    })

    print(f"  rows before cleaning : {before}")
    print(f"  dropped (grand total / unparseable ID / missing amount): {n_dropped_bad_amount}")
    print(f"  dropped (sanction amount <= 0)                        : {n_dropped_nonpositive}")
    print(f"  rows after cleaning  : {len(out)}")
    print(f"  IDA missing (flagged, kept as 'Unknown'): {int(out['ida_missing'].sum())}")
    return out


def load_completed():
    print(f"\n[Completed] reading {COMPLETED_CSV}")
    df = pd.read_csv(COMPLETED_CSV, skiprows=1)
    before = len(df)

    df = df[df["Sr. No."] != "Grand Total"].copy()

    df["work_id"] = df["Work"].apply(extract_work_id)
    df["amount_disbursed"] = clean_amount(df["Amount Disbursed ( ₹ )"])
    df["amount_missing"] = df["amount_disbursed"].isna()
    df["completion_date"] = pd.to_datetime(df["Completion Date"], format=RAW_DATE_FORMAT, errors="coerce")

    df["ida_missing"] = df["IDA"].isna() | (df["IDA"].astype(str).str.strip() == "")
    df["IDA"] = df["IDA"].fillna("Unknown")
    df.loc[df["IDA"].astype(str).str.strip() == "", "IDA"] = "Unknown"

    # Drop only rows with no parseable Work ID (needed as the join key downstream)
    df = df.dropna(subset=["work_id"])
    n_dropped_bad_id = before - len(df)

    # Data-error removal: non-positive disbursed amounts (NaN/missing is fine and KEPT)
    n_before_error_check = len(df)
    df = df[(df["amount_disbursed"] > 0) | (df["amount_disbursed"].isna())]
    n_dropped_nonpositive = n_before_error_check - len(df)

    out = pd.DataFrame({
        "work_id": df["work_id"],
        "sl_no": pd.to_numeric(df["Sr. No."], errors="coerce"),
        "work_raw": df["Work"],
        "work_category": clean_text(df["Work Category"]),
        "state": clean_text(df["State"]),
        "ida": df["IDA"],
        "ida_missing": df["ida_missing"],
        "mp_name": clean_text(df["Hon'ble Members of Parliament"]),
        "constituency": clean_text(df["Constituency"]),
        "work_description": clean_text(df["Work Description"]),
        "completion_date": df["completion_date"].dt.date,
        "amount_disbursed": df["amount_disbursed"],
        "amount_missing": df["amount_missing"],
    })

    print(f"  rows before cleaning : {before}")
    print(f"  dropped (grand total / unparseable Work ID): {n_dropped_bad_id}")
    print(f"  dropped (amount disbursed <= 0)             : {n_dropped_nonpositive}")
    print(f"  rows after cleaning  : {len(out)}")
    print(f"  Amount Disbursed missing (kept, flagged): {int(out['amount_missing'].sum())}")
    return out


def load_allocations():
    print(f"\n[Allocations] reading {ALLOCATION_CSV}")
    df = pd.read_csv(ALLOCATION_CSV, skiprows=1)
    before = len(df)

    df = df[df["Sr. No."] != "Grand Total"].copy()
    df["allocated_amount"] = clean_amount(df["Allocated AMOUNT ( ₹ )"])
    df = df.dropna(subset=["allocated_amount"])
    df = df[df["allocated_amount"] > 0]

    out = pd.DataFrame({
        "sl_no": pd.to_numeric(df["Sr. No."], errors="coerce"),
        "state": clean_text(df["State"]),
        "mp_name": clean_text(df["Hon'ble Members of Parliaments"]),
        "constituency": clean_text(df["Constituency"]),
        "allocated_amount": df["allocated_amount"],
    })

    print(f"  rows before cleaning : {before}")
    print(f"  rows after cleaning  : {len(out)}")
    return out


def load_to_sqlite(df_sanctioned, df_completed, df_allocations):
    print("\n[DB] (re)creating tables and loading rows ...")
    init_db()

    # Wipe existing rows so re-running preprocess.py is idempotent
    db = SessionLocal()
    db.query(WorkSanctioned).delete()
    db.query(WorkCompleted).delete()
    db.query(MPAllocation).delete()
    db.commit()
    db.close()

    df_sanctioned.to_sql("works_sanctioned", engine, if_exists="append", index=False)
    df_completed.to_sql("works_completed", engine, if_exists="append", index=False)
    df_allocations.to_sql("mp_allocations", engine, if_exists="append", index=False)
    print("  done.")


def main():
    df_s = load_sanctioned()
    df_c = load_completed()
    df_a = load_allocations()
    load_to_sqlite(df_s, df_c, df_a)

    print("\n" + "=" * 70)
    print("SAMPLE CLEANED ROWS")
    print("=" * 70)
    print("\n-- works_sanctioned (3 rows) --")
    print(df_s.sample(min(3, len(df_s)), random_state=42).to_string())
    print("\n-- works_completed (3 rows) --")
    print(df_c.sample(min(3, len(df_c)), random_state=42).to_string())
    print("\n-- mp_allocations (3 rows) --")
    print(df_a.sample(min(3, len(df_a)), random_state=42).to_string())

    print("\n" + "=" * 70)
    print("FINAL ROW COUNTS LOADED INTO SQLite")
    print("=" * 70)
    print(f"  works_sanctioned : {len(df_s)}")
    print(f"  works_completed  : {len(df_c)}")
    print(f"  mp_allocations   : {len(df_a)}")
    matched = df_s["work_id"].isin(set(df_c["work_id"])).sum()
    print(f"  (info) sanctioned rows with a matching completed record: {matched} "
          f"({matched/len(df_s):.1%})")


if __name__ == "__main__":
    main()
