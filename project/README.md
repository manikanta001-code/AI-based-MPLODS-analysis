# MPLADS AI Monitoring Platform

AI-powered monitoring and analytics platform for MPLADS (Members of Parliament
Local Area Development Scheme) fund utilization and project execution — built
for Smart India Hackathon (MoSPI problem statement).

Trained and tested end-to-end on your real data: **49,000 sanctioned works**,
**33,960 completed works**, and **542 MP fund allocations**, across every
state and union territory.

---

## What's in here

```
project/
├── data/                          # your 3 raw MPLADS export files
├── requirements.txt                # Python deps (backend + ML)
├── backend/
│   ├── config.py                   # all paths, weights, thresholds — edit paths here
│   ├── database.py                 # SQLAlchemy models (3 staging tables)
│   ├── db_utils.py                 # SQL query + role-scoping helpers for the API
│   ├── auth.py                     # JWT auth, 4 demo accounts
│   ├── main.py                     # FastAPI app entrypoint
│   ├── etl/
│   │   ├── preprocess.py           # Phase 1: clean 3 CSVs → SQLite
│   │   └── feature_engine.py       # Phase 2: joins + derived ML features
│   ├── ml/
│   │   ├── anomaly_detector.py     # IsolationForest + LOF + per-category PCA
│   │   ├── delay_model.py          # RandomForest delay-risk classifier
│   │   ├── cost_model.py           # GradientBoosting cost-overrun regressor
│   │   ├── duplicate_finder.py     # TF-IDF + cosine + thefuzz confirmation
│   │   ├── explain.py              # ML outputs → plain-English reasons
│   │   ├── evaluate.py             # metrics, synthetic-anomaly test, charts
│   │   ├── train.py                # runs the full training pipeline
│   │   ├── scorer.py               # scores newly-uploaded data (no retrain)
│   │   └── artifacts/              # .pkl models + metrics.json (generated)
│   └── routers/                    # works, alerts, analytics, roles, meta, upload
└── frontend/
    ├── src/pages/                  # Login + 4 dashboards + Alerts/Upload/Detail
    ├── src/components/              # Sidebar, KPICard, RiskTable, charts, etc.
    └── src/api/, src/context/       # API client, auth context
```

---

## Prerequisites

- **Python 3.10+**
- **Node.js 18+** and npm
- The 3 raw CSV files already sit in `project/data/` — if you're starting
  from a fresh copy of this project, make sure `Works_Sanctioned.csv`,
  `Works_Completed_1.csv`, and `Allocated_Limit_for_Honble_MPs__4_.csv` are
  in that folder before running anything.

---

## Setup — Windows (Command Prompt or PowerShell)

```bat
cd project

:: 1. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate

:: 2. Install Python dependencies
pip install -r requirements.txt

:: 3. Clean the raw data into SQLite (Phase 1)
cd backend
python etl/preprocess.py

:: 4. Train all ML models (Phase 2) — takes ~1-2 minutes on 49,000 rows
python ml/train.py

:: 5. Start the API server (leave this terminal running)
uvicorn main:app --reload --port 8000
```

Open a **second** terminal for the frontend:

```bat
cd project\frontend
npm install
npm run dev
```

Open **http://localhost:5173** in your browser and click any demo account
tile to sign in.

## Setup — macOS / Linux

Identical, just use `source venv/bin/activate` instead of `venv\Scripts\activate`.

```bash
cd project
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cd backend
python etl/preprocess.py
python ml/train.py
uvicorn main:app --reload --port 8000
```

```bash
# second terminal
cd project/frontend
npm install
npm run dev
```

---

## Demo accounts

No user table exists in the source data, so 4 fixed accounts are pre-scoped
to real, interesting entities in your dataset:

| Username           | Password       | Role     | Scoped to                                    |
|---------------------|----------------|----------|-----------------------------------------------|
| `ministry`          | `ministry123`  | Ministry | All India                                     |
| `state_up`          | `state123`     | State    | Uttar Pradesh (9,163 works — largest state)   |
| `mp_priya_saroj`    | `mp123`        | MP       | MP Priya Saroj (377 real High-risk works)     |
| `district_jaunpur`  | `district123`  | District | Jaunpur (1,421 works — largest district)      |

Role-based access is enforced **server-side** (not just hidden in the UI) —
e.g. an MP token cannot pull another state's data even by editing the URL.

---

## Trying the early-warning upload demo

1. Sign in as `ministry` or `state_up` (only these two roles can upload).
2. Go to **Upload Data** in the sidebar.
3. Upload a CSV/Excel file with the same columns as `Works_Sanctioned.csv`
   (Sl No., Work Category, Work, State, IDA, Hon'ble Members of Parliament,
   Constituency, Work description, Recommended date, Sanction Date,
   Sanction Amount ( ₹ ), Work Status).
4. Click **Score with AI models** — results come back in a few seconds using
   the models already trained in step 4 above (no retraining happens).

---

## Re-running the pipeline

Both `etl/preprocess.py` and `ml/train.py` are safe to re-run any time (they
replace their own tables/files rather than appending) — useful if you swap
in updated source CSVs later. Re-run both, in that order, then restart
`uvicorn`.

---

## Real results from your data (Phase 2 training run)

| Model                        | Metric                          | Result            |
|-------------------------------|----------------------------------|--------------------|
| Delay model (RandomForest)     | Precision / Recall / F1          | 0.72 / 0.80 / 0.76 |
| Cost model (GradientBoosting)  | MAE / R²                         | ₹9,488 / 0.984     |
| Anomaly ensemble               | Synthetic-injection detection rate| 89.7% (269/300)    |
| Risk bands across all 49,000 works | High / Medium / Low         | 2,247 / 28,864 / 17,889 |

See `backend/ml/artifacts/metrics.json` and `feature_importance.png` after
running `ml/train.py` for the full evaluation output.

---

## Known notes / design decisions worth knowing

- **Frontend is React + Vite, not Next.js.** This is a client-rendered SPA
  talking to a separate FastAPI backend — there's no server-side-rendering
  need, so Vite keeps the local run story to two plain `npm`/`uvicorn`
  commands instead of also standing up a Node SSR server.
- **Districts aren't a column in the source data** — they're derived from
  the `IDA` (Implementing/Developmental Agency) field, which is formatted
  as `"DISTRICT NAME(DISTRICT MAGISTRATE ... )"`. 718 districts extracted
  this way.
- **Duplicate-work flags are ~31% of all works.** Checked against real
  examples — this is genuine, not a bug: MPLADS work descriptions are
  heavily templated (e.g. "X's house nearby"), so many truly are
  near-identical text. This is why duplicate similarity only carries 15%
  weight in the fused Risk Score rather than dominating it.
- **Cost risk is 0 for any work still in progress** — it's only computable
  once a work is completed and has an actual disbursed amount to compare
  against the ML-predicted expectation. This is intentional, not a missing
  feature.
- All amounts in the UI are shown in **₹ Lakh/Crore** (Indian numbering),
  matching how the source data and MPLADS reporting conventions work.

---

## Troubleshooting

- **`bcrypt` version errors during `pip install`**: some `passlib`/`bcrypt`
  combinations conflict; the pinned versions in `requirements.txt` are
  verified to work together. If you still hit issues, `pip install
  bcrypt==4.1.3 --force-reinstall`.
- **Frontend shows "Cannot reach the server"**: the FastAPI backend isn't
  running, or isn't on port 8000. Check the first terminal.
- **`python etl/preprocess.py` can't find the CSVs**: edit the three paths
  at the top of `backend/config.py` to point at wherever your CSV files
  actually are.
- **Port already in use**: another process is on 8000 or 5173 — stop it, or
  run `uvicorn main:app --port 8001` (and update `frontend/vite.config.js`'s
  proxy target to match).
