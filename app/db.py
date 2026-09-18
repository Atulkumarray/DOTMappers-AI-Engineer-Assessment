import sqlite3
from pathlib import Path
import pandas as pd

from .config import DATA_PATH, DB_PATH

SCHEMA_COLUMNS = [
    "ticket_id", "created_at", "category", "priority", "status",
    "response_time_hrs", "resolution_time_hrs", "agent_id",
    "customer_rating", "issue_summary"
]

def get_connection(read_only: bool = False) -> sqlite3.Connection:
    if read_only:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, check_same_thread=False)
    else:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_database() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(DATA_PATH)
    missing = [c for c in SCHEMA_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Dataset is missing required columns: {missing}")

    df = df[SCHEMA_COLUMNS].copy()
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    if df["created_at"].isna().any():
        raise ValueError("created_at contains invalid timestamps")

    conn = get_connection()
    try:
        df.to_sql("support_tickets", conn, if_exists="replace", index=False)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tickets_status ON support_tickets(status)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tickets_priority ON support_tickets(priority)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tickets_category ON support_tickets(category)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tickets_agent ON support_tickets(agent_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tickets_created_at ON support_tickets(created_at)"
        )
        conn.commit()
    finally:
        conn.close()

def dataset_metadata() -> dict:
    conn = get_connection(read_only=True)
    try:
        row = conn.execute("""
            SELECT COUNT(*) AS row_count,
                   MIN(created_at) AS min_created_at,
                   MAX(created_at) AS max_created_at
            FROM support_tickets
        """).fetchone()
        return dict(row)
    finally:
        conn.close()
