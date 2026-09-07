"""
routers/upload.py
────────────────────
/api/upload — the early-warning demo endpoint judges actually interact
with: upload a CSV/Excel of newly-recommended works (same raw column
format as Works_Sanctioned.csv) and get back ML risk scores + plain-
English reasons in seconds, using the models trained once in Phase 2
(ml/train.py) — no retraining happens here, see ml/scorer.py.

ACCESS: restricted to ministry and state roles — uploading a new batch of
works for oversight scoring is an administrative function, not something
an individual MP or district office does in this platform's workflow.
"""

import os
import shutil
import tempfile

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File

from auth import require_roles, CurrentUser
from ml.scorer import score_uploaded_file

router = APIRouter(prefix="/api/upload", tags=["upload"])

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


@router.post("")
async def upload_and_score(
    file: UploadFile = File(...),
    user: CurrentUser = Depends(require_roles("ministry", "state")),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type '{ext}'. Upload a .csv or .xlsx file.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        scored_df, n_dropped_during_cleaning = score_uploaded_file(tmp_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scoring failed: {e}")
    finally:
        os.unlink(tmp_path)

    # State-role uploads are still scoped to their own state for the results view
    if user.role == "state":
        scored_df = scored_df[scored_df["state"].str.casefold() == (user.scope or "").casefold()]

    results = scored_df.to_dict(orient="records")
    for r in results:
        r["reasons"] = r.pop("risk_reasons").split("; ")

    return {
        "filename": file.filename,
        "rows_uploaded": len(results) + n_dropped_during_cleaning,
        "rows_dropped_during_cleaning": n_dropped_during_cleaning,
        "rows_scored": len(results),
        "high_risk_count": sum(1 for r in results if r["risk_band"] == "High"),
        "medium_risk_count": sum(1 for r in results if r["risk_band"] == "Medium"),
        "low_risk_count": sum(1 for r in results if r["risk_band"] == "Low"),
        "results": sorted(results, key=lambda r: r["risk_score"], reverse=True),
    }
