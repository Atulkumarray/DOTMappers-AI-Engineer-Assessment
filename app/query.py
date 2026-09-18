import re
import sqlite3
from datetime import datetime
from typing import Any

from .anomaly import anomalies
from .llm import generate_sql

FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|ATTACH|DETACH|PRAGMA|REPLACE|VACUUM|REINDEX)\b",
    re.IGNORECASE,
)


def validate_sql(sql: str) -> str:
    sql = sql.strip()
    if not sql:
        raise ValueError("LLM returned empty SQL")
    if ";" in sql.rstrip(";"):
        raise ValueError("Multiple SQL statements are not allowed")
    if FORBIDDEN.search(sql):
        raise ValueError("Only read-only SQL is allowed")
    if not re.match(r"^(SELECT|WITH)\b", sql, re.IGNORECASE):
        raise ValueError("Query must start with SELECT or WITH")
    if not re.search(r"\bsupport_tickets\b", sql, re.IGNORECASE):
        raise ValueError("Query must use support_tickets")
    if re.search(r"\b(sqlite_master|sqlite_schema|sqlite_temp_master)\b", sql, re.IGNORECASE):
        raise ValueError("SQLite metadata tables are not allowed")
    return sql.rstrip(";")


def execute_sql(conn: sqlite3.Connection, sql: str) -> list[dict[str, Any]]:
    cursor = conn.execute(sql)
    columns = [description[0] for description in cursor.description] if cursor.description else []
    return [{column: row[column] for column in columns} for row in cursor.fetchall()]


def _month_fallback(conn: sqlite3.Connection) -> dict:
    latest = conn.execute("SELECT MAX(created_at) AS latest FROM support_tickets").fetchone()["latest"]
    latest_date = datetime.fromisoformat(latest)
    start = latest_date.replace(day=1).strftime("%Y-%m-%d %H:%M")
    if latest_date.month == 12:
        next_month = latest_date.replace(year=latest_date.year + 1, month=1, day=1)
    else:
        next_month = latest_date.replace(month=latest_date.month + 1, day=1)
    end = next_month.strftime("%Y-%m-%d %H:%M")
    sql = f"""SELECT agent_id, COUNT(*) AS resolved_tickets
              FROM support_tickets
              WHERE status = 'Resolved' AND created_at >= '{start}' AND created_at < '{end}'
              GROUP BY agent_id
              ORDER BY resolved_tickets DESC, agent_id
              LIMIT 1"""
    return sql


def fallback_query(conn: sqlite3.Connection, question: str) -> dict:
    q = question.lower().strip()
    explanation = "Deterministic fallback used because the configured LLM was unavailable."

    if "anomal" in q and "resolution" in q:
        period = "week" if "week" in q else "month" if "month" in q else "all"
        report = anomalies(conn, period=period)
        return {
            "answer": report,
            "rows": [],
            "sql": None,
            "explanation": explanation + " The anomaly engine applies the requested time window.",
        }

    if "how many" in q and "open" in q:
        sql = "SELECT COUNT(*) AS open_tickets FROM support_tickets WHERE status = 'Open'"
    elif "critical" in q and ("unresolved" in q or "not resolved" in q):
        if "within" in q:
            match = re.search(r"within\s+(\d+(?:\.\d+)?)\s*hours?", q)
            hours = float(match.group(1)) if match else 12.0
            sql = f"""SELECT ticket_id, created_at, category, priority, status,
                      resolution_time_hrs, agent_id, issue_summary
                      FROM support_tickets
                      WHERE priority = 'Critical' AND status != 'Resolved'
                      AND (resolution_time_hrs IS NULL OR resolution_time_hrs > {hours})
                      ORDER BY created_at"""
        else:
            sql = """SELECT COUNT(*) AS critical_unresolved
                     FROM support_tickets
                     WHERE priority = 'Critical' AND status != 'Resolved'"""
    elif "average customer rating" in q and "technical" in q:
        sql = """SELECT ROUND(AVG(customer_rating), 2) AS average_customer_rating
                 FROM support_tickets
                 WHERE category = 'Technical' AND customer_rating IS NOT NULL"""
    elif "lowest average" in q and "rating" in q and "agent" in q:
        sql = """SELECT agent_id, ROUND(AVG(customer_rating), 2) AS average_customer_rating
                 FROM support_tickets
                 WHERE customer_rating IS NOT NULL
                 GROUP BY agent_id
                 ORDER BY average_customer_rating ASC, agent_id
                 LIMIT 1"""
    elif "most tickets" in q and "agent" in q and "resolved" in q:
        sql = _month_fallback(conn) if "month" in q else """SELECT agent_id, COUNT(*) AS resolved_tickets
                 FROM support_tickets
                 WHERE status = 'Resolved'
                 GROUP BY agent_id
                 ORDER BY resolved_tickets DESC, agent_id
                 LIMIT 1"""
    else:
        raise ValueError(
            "LLM unavailable and this question is outside the built-in fallback examples. Start Ollama and retry."
        )

    rows = execute_sql(conn, sql)
    return {"answer": rows, "rows": rows, "sql": sql, "explanation": explanation}


def answer_question(conn: sqlite3.Connection, question: str) -> dict:
    if not question or not question.strip():
        raise ValueError("Question cannot be empty")

    latest = conn.execute("SELECT MAX(created_at) AS latest FROM support_tickets").fetchone()["latest"]

    try:
        plan = generate_sql(question, latest)
        sql = validate_sql(plan["sql"])
        rows = execute_sql(conn, sql)
        return {
            "answer": rows,
            "rows": rows,
            "sql": sql,
            "explanation": plan.get("explanation", ""),
            "llm_used": True,
        }
    except Exception as llm_error:
        result = fallback_query(conn, question)
        result["llm_used"] = False
        result["llm_error"] = str(llm_error)
        return result
