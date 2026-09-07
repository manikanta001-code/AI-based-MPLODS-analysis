"""
config.py
─────────
Single place for paths, thresholds and weights so nothing is hardcoded
inside the pipeline logic itself. EDIT THE THREE PATHS BELOW to point at
your local copies of the raw MPLADS exports before running anything.
"""

import os

# ──────────────────────────────────────────────────────────────────────
# 1. RAW DATA FILE PATHS  <-- EDIT THESE ONCE FOR YOUR MACHINE
# ──────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))          # .../project/backend
DATA_DIR = os.path.join(BASE_DIR, "..", "data")                 # .../project/data

SANCTIONED_CSV = os.path.join(DATA_DIR, "Works_Sanctioned.csv")
COMPLETED_CSV = os.path.join(DATA_DIR, "Works_Completed_1.csv")
ALLOCATION_CSV = os.path.join(DATA_DIR, "Allocated_Limit_for_Honble_MPs__4_.csv")

# ──────────────────────────────────────────────────────────────────────
# 2. DATABASE
# ──────────────────────────────────────────────────────────────────────
DB_PATH = os.path.join(BASE_DIR, "mplads.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

# ──────────────────────────────────────────────────────────────────────
# 3. MODEL ARTIFACT PATHS (used from Phase 2 onward)
# ──────────────────────────────────────────────────────────────────────
MODEL_DIR = os.path.join(BASE_DIR, "ml", "artifacts")
os.makedirs(MODEL_DIR, exist_ok=True)

ISOLATION_FOREST_PATH = os.path.join(MODEL_DIR, "isolation_forest.pkl")
LOF_PATH = os.path.join(MODEL_DIR, "lof.pkl")
DELAY_MODEL_PATH = os.path.join(MODEL_DIR, "delay_model.pkl")
COST_MODEL_PATH = os.path.join(MODEL_DIR, "cost_model.pkl")
SCALER_PATH = os.path.join(MODEL_DIR, "scaler.pkl")
ENCODER_PATH = os.path.join(MODEL_DIR, "encoders.pkl")
TFIDF_PATH = os.path.join(MODEL_DIR, "tfidf.pkl")
METRICS_PATH = os.path.join(MODEL_DIR, "metrics.json")
FEATURE_IMPORTANCE_PNG = os.path.join(MODEL_DIR, "feature_importance.png")

# ──────────────────────────────────────────────────────────────────────
# 4. RISK FUSION WEIGHTS (used from Phase 2 onward — Section E of spec)
#    Risk_Score = 0.35*Anomaly + 0.30*Delay_Risk + 0.20*Cost_Risk + 0.15*Duplicate_Score
# ──────────────────────────────────────────────────────────────────────
RISK_WEIGHTS = {
    "anomaly": 0.35,
    "delay": 0.30,
    "cost": 0.20,
    "duplicate": 0.15,
}

RISK_HIGH_THRESHOLD = 70   # Risk_Score >= 70  -> High
RISK_MEDIUM_THRESHOLD = 40  # 40 <= Risk_Score < 70 -> Medium; below -> Low

# IsolationForest contamination (expected proportion of anomalies)
IF_CONTAMINATION = 0.05

# A completed work taking > this multiple of its category's median duration
# is self-supervised-labeled as "delayed" for training the delay classifier.
DELAY_LABEL_MULTIPLIER = 1.5

# thefuzz token_set_ratio confirmation threshold for duplicate detection
DUPLICATE_FUZZY_THRESHOLD = 90

# ──────────────────────────────────────────────────────────────────────
# 5. DATE FORMAT used consistently across all three raw files
#    e.g. "08-Jul-2024"
# ──────────────────────────────────────────────────────────────────────
RAW_DATE_FORMAT = "%d-%b-%Y"

# ──────────────────────────────────────────────────────────────────────
# 6. DEMO USER ACCOUNTS (Phase 3 — auth.py)
#    No user table exists in the source data, so these 4 fixed demo
#    accounts are used for the judges' demo / local testing. Each
#    non-ministry account is pre-scoped to a REAL entity in the dataset
#    chosen to make a good demo (see auth.py docstring for why):
#      - state_up: Uttar Pradesh (9,163 works, the largest state)
#      - mp_priya_saroj: MP "PRIYA SAROJ" (377 High-risk works)
#      - district_jaunpur: Jaunpur district (1,421 works, largest district)
#    scope for role="district" matches the exact `ida` column value.
# ──────────────────────────────────────────────────────────────────────
DEMO_USERS_RAW = {
    "ministry": {"password": "ministry123", "role": "ministry", "scope": None,
                 "display_name": "Ministry of Statistics & Programme Implementation"},
    "state_up": {"password": "state123", "role": "state", "scope": "Uttar Pradesh",
                 "display_name": "Uttar Pradesh State Nodal Authority"},
    "mp_priya_saroj": {"password": "mp123", "role": "mp", "scope": "PRIYA SAROJ",
                        "display_name": "Hon'ble MP Priya Saroj"},
    "district_jaunpur": {"password": "district123", "role": "district",
                          "scope": "JAUNPUR(DISTRICT MAGISTRATE JAUNPUR_IDA)",
                          "display_name": "Jaunpur District Authority"},
}

# ──────────────────────────────────────────────────────────────────────
# 6. AUTH (Phase 3)
# ──────────────────────────────────────────────────────────────────────
# NOTE: for a real deployment this must come from an environment variable,
# never a hardcoded string. Hardcoded here only because this is a hackathon
# demo build with no secrets-management infra.
JWT_SECRET_KEY = "sih-mplads-demo-secret-change-in-production-3f9a7c2e"
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 hours — long enough for a demo/judging session

# Demo accounts. Each non-ministry role is bound to a REAL entity from your
# dataset (chosen because it has a meaningful volume of works, for a good
# demo) so that role-based scoping is actually real, not decorative:
#   - an 'mp' user can ONLY ever see PRIYA SAROJ's own works
#   - a 'state' user can ONLY ever see Uttar Pradesh's works
#   - a 'district' user can ONLY ever see JAUNPUR's works
#   - 'ministry' is unrestricted (sees/filters across all states/MPs/districts)
# password hashes are bcrypt of the plaintext passwords shown in the comment.
DEMO_USERS = {
    "ministry": {
        "password": "ministry123",
        "role": "ministry",
        "scope": None,
        "display_name": "Ministry of Statistics & Programme Implementation (MoSPI)",
    },
    "mp_priya_saroj": {
        "password": "mp123",
        "role": "mp",
        "scope": "PRIYA SAROJ",
        "display_name": "Priya Saroj, MP",
    },
    "state_up": {
        "password": "state123",
        "role": "state",
        "scope": "Uttar Pradesh",
        "display_name": "Uttar Pradesh State Nodal Authority",
    },
    "district_jaunpur": {
        "password": "district123",
        "role": "district",
        "scope": "JAUNPUR(DISTRICT MAGISTRATE JAUNPUR_IDA)",
        "display_name": "Jaunpur District Authority",
    },
}

