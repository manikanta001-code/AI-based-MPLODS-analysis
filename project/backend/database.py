"""
database.py
───────────
SQLAlchemy engine/session setup + ORM table definitions.

We keep THREE staging tables that mirror the three raw source files
(works_sanctioned, works_completed, mp_allocations) rather than force-joining
them into one table during ETL. Why:
  - "Work ID" only has ~59% overlap between Sanctioned and Completed
    (Sanctioned = current-term snapshot, Completed spans a longer history),
    so a hard join at ETL time would silently drop real records.
  - Phase 2 (feature_engine.py) needs BOTH the sanctioned-side fields
    (recommended/sanction dates, sanction amount, status) and the
    completed-side fields (completion date, amount disbursed) to engineer
    delay/cost-overrun features — it performs the join itself, on demand,
    with full control over how unmatched rows are handled.
  - This is lossless: nothing from the raw files is discarded at this stage.
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, Date, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker

from config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class WorkSanctioned(Base):
    """One row per MPLADS work recommendation/sanction (Works_Sanctioned.csv)."""
    __tablename__ = "works_sanctioned"

    id = Column(Integer, primary_key=True, autoincrement=True)
    work_id = Column(String, index=True, nullable=False)       # extracted from "Work" column, join key
    sl_no = Column(Integer)
    work_raw = Column(String)                                   # original "Work" cell, kept for traceability
    work_category = Column(String, index=True)
    state = Column(String, index=True)
    ida = Column(String)
    ida_missing = Column(Boolean, default=False)                # red-flag: IDA was blank in source data
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
    amount_disbursed = Column(Float, nullable=True)             # nullable: missing values are kept, not dropped
    amount_missing = Column(Boolean, default=False)


class MPAllocation(Base):
    """One row per MP's total allocated MPLADS limit (Allocated_Limit_for_Honble_MPs.csv)."""
    __tablename__ = "mp_allocations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sl_no = Column(Integer)
    state = Column(String, index=True)
    mp_name = Column(String, index=True)
    constituency = Column(String, index=True)
    allocated_amount = Column(Float)


def init_db():
    """Create all tables (drops nothing; safe to call repeatedly)."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency — yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
