"""
database.py
───────────
SQLAlchemy engine/session setup + ORM table definitions.
Includes raw staging tables and processed feature tables (work_risk_scores).
"""

import os
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, Float, Date, Boolean, text
from sqlalchemy.orm import declarative_base, sessionmaker

from config import DATABASE_URL

# SQLite needs this special flag; Postgres does not support it at all.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class WorkSanctioned(Base):
    """One row per MPLADS work recommendation/sanction (Works_Sanctioned.csv)."""
    __tablename__ = "works_sanctioned"

    id = Column(Integer, primary_key=True, autoincrement=True)
    work_id = Column(String, index=True, nullable=False)
    sl_no = Column(Integer)
    work_raw = Column(String)
    work_category = Column(String, index=True)
    state = Column(String, index=True)
    ida = Column(String)
    ida_missing = Column(Boolean, default=False)
    mp_name = Column(String, index=True)
    constituency = Column(String, index=True)
    work_description = Column(String)
    recommended_date = Column(Date)
    sanction_date = Column(Date)
    sanction_amount = Column(Float)
    work_status = Column(String, index=True)


class WorkCompleted(Base):
    """One row per completed MPLADS work (Works_Completed_1.csv)."""
    __tablename__ = "works_completed"

    id = Column(Integer, primary_key=True, autoincrement=True)
    work_id = Column(String, index=True, nullable=False)
    sl_no = Column(Integer)
    work_raw = Column(String)
    work_category = Column(String, index=True)
    state = Column(String, index=True)
    ida = Column(String)
    ida_missing = Column(Boolean, default=False)
    mp_name = Column(String, index=True)
    constituency = Column(String, index=True)
    work_description = Column(String)
    completion_date = Column(Date)
    amount_disbursed = Column(Float, nullable=True)
    amount_missing = Column(Boolean, default=False)


class MPAllocation(Base):
    """One row per MP's total allocated MPLADS limit."""
    __tablename__ = "mp_allocations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sl_no = Column(Integer)
    state = Column(String, index=True)
    mp_name = Column(String, index=True)
    constituency = Column(String, index=True)
    allocated_amount = Column(Float)


class WorkRiskScore(Base):
    """Processed analytics & feature table required by routers.

    NOTE: this simplified ORM definition is only used to make sure the
    table exists on first boot. The real, full schema (with all ML
    feature columns like ida, expected_cost, risk_reasons, etc.) comes
    from work_risk_scores.csv and is loaded with if_exists="replace" in
    init_db(), which lets pandas create the table with the exact columns
    present in that CSV. All API queries use raw SQL against the actual
    table, not this class, so this simplified version never causes a
    mismatch in practice.
    """
    __tablename__ = "work_risk_scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    work_id = Column(String, index=True)
    state = Column(String, index=True)
    district = Column(String, index=True)
    mp_name = Column(String, index=True)
    constituency = Column(String, index=True)
    work_category = Column(String, index=True)
    sanction_date = Column(String)
    completion_date = Column(String)
    sanction_amount = Column(Float)
    amount_disbursed = Column(Float)
    is_completed = Column(Integer, default=0)
    risk_band = Column(String, index=True)
    delay_risk_pct = Column(Float)
    risk_score = Column(Float)


def init_db():
    """Create all tables and build features if they don't exist yet."""
    Base.metadata.create_all(bind=engine)

    # Check if work_risk_scores contains data
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM work_risk_scores")).fetchone()
        row_count = result[0] if result else 0

    # Auto-run feature generator / ETL if table is empty
    if row_count == 0:
        print("Table 'work_risk_scores' is empty. Populating initial dataset...")
        try:
            # If you have a script like feature_engine.py or a CSV pre-baked:
            import feature_engine
            feature_engine.run_feature_pipeline()
        except ImportError:
            # Fallback if CSV dataset exists directly in the workspace.
            # if_exists="replace" recreates the table using the CSV's own
            # real columns/types, so it always matches the actual data
            # regardless of what the simplified ORM class above defines.
            csv_path = os.path.join(os.path.dirname(__file__), "work_risk_scores.csv")
            if os.path.exists(csv_path):
                df = pd.read_csv(csv_path)
                df.to_sql("work_risk_scores", con=engine, if_exists="replace", index=False)
                print("Successfully populated work_risk_scores from CSV.")


def get_db():
    """FastAPI dependency — yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
