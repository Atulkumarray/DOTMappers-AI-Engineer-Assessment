import re
import sqlite3
from datetime import datetime, timedelta
from typing import List, Optional, Tuple


def _latest_timestamp(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT MAX(created_at) AS latest FROM support_tickets"
    ).fetchone()
    return row["latest"]


def _percentile(sorted_values: List[float], p: float) -> float:
    n = len(sorted_values)

    if n == 1:
        return sorted_values[0]

    pos = (n - 1) * p
    lo = int(pos)
    hi = min(lo + 1, n - 1)

    return sorted_values[lo] + (
        sorted_values[hi] - sorted_values[lo]
    ) * (pos - lo)


def resolution_outliers(
    conn: sqlite3.Connection,
    start_at: Optional[str] = None,
    end_at: Optional[str] = None
) -> dict:
    filters = ["resolution_time_hrs IS NOT NULL"]
    params: List[str] = []

    if start_at:
        filters.append("created_at >= ?")
        params.append(start_at)

    if end_at:
        filters.append("created_at <= ?")
        params.append(end_at)

    where = " AND ".join(filters)

    rows = conn.execute(
        "SELECT resolution_time_hrs "
        "FROM support_tickets "
        "WHERE {} "
        "ORDER BY resolution_time_hrs".format(where),
        params,
    ).fetchall()

    values = [
        float(row["resolution_time_hrs"])
        for row in rows
    ]

    if not values:
        return {
            "method": "IQR",
            "threshold_hours": None,
            "tickets": [],
            "sample_size": 0,
        }

    q1 = _percentile(values, 0.25)
    q3 = _percentile(values, 0.75)
    iqr = q3 - q1
    threshold = q3 + 1.5 * iqr

    ticket_filters = [
        "resolution_time_hrs IS NOT NULL",
        "resolution_time_hrs > ?",
    ]

    ticket_params: List[object] = [threshold]

    if start_at:
        ticket_filters.append("created_at >= ?")
        ticket_params.append(start_at)

    if end_at:
        ticket_filters.append("created_at <= ?")
        ticket_params.append(end_at)

    ticket_rows = conn.execute(
        """
        SELECT ticket_id,
               created_at,
               category,
               priority,
               status,
               response_time_hrs,
               resolution_time_hrs,
               agent_id,
               customer_rating,
               issue_summary
        FROM support_tickets
        WHERE {}
        ORDER BY resolution_time_hrs DESC
        """.format(" AND ".join(ticket_filters)),
        ticket_params,
    ).fetchall()

    return {
        "method": "IQR",
        "q1_hours": round(q1, 2),
        "q3_hours": round(q3, 2),
        "iqr_hours": round(iqr, 2),
        "threshold_hours": round(threshold, 2),
        "sample_size": len(values),
        "tickets": [dict(row) for row in ticket_rows],
    }


def unresolved_priority_old(
    conn: sqlite3.Connection,
    age_hours: float = 24.0,
    reference_timestamp: Optional[str] = None,
    start_at: Optional[str] = None,
    end_at: Optional[str] = None,
) -> dict:

    latest = reference_timestamp or _latest_timestamp(conn)

    filters = [
        "status != 'Resolved'",
        "priority IN ('High', 'Critical')",
        "((julianday(?) - julianday(created_at)) * 24.0) > ?",
    ]

    params: List[object] = [
        latest,
        age_hours,
    ]

    if start_at:
        filters.append("created_at >= ?")
        params.append(start_at)

    if end_at:
        filters.append("created_at <= ?")
        params.append(end_at)

    rows = conn.execute(
        """
        SELECT ticket_id,
               created_at,
               category,
               priority,
               status,
               response_time_hrs,
               resolution_time_hrs,
               agent_id,
               customer_rating,
               issue_summary,
               ROUND(
                   (julianday(?) - julianday(created_at)) * 24.0,
                   2
               ) AS age_hours
        FROM support_tickets
        WHERE {}
        ORDER BY age_hours DESC
        """.format(" AND ".join(filters)),
        [latest] + params,
    ).fetchall()

    return {
        "reference_timestamp": latest,
        "age_threshold_hours": age_hours,
        "tickets": [dict(row) for row in rows],
    }


def _week_window(latest: datetime) -> Tuple[str, str]:
    start = latest - timedelta(days=latest.weekday())

    start = start.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    end = start + timedelta(
        days=6,
        hours=23,
        minutes=59,
        seconds=59,
    )

    return (
        start.strftime("%Y-%m-%d %H:%M"),
        end.strftime("%Y-%m-%d %H:%M"),
    )


def _month_window(latest: datetime) -> Tuple[str, str]:
    start = latest.replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    if latest.month == 12:
        next_month = latest.replace(
            year=latest.year + 1,
            month=1,
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
    else:
        next_month = latest.replace(
            month=latest.month + 1,
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

    end = next_month - timedelta(minutes=1)

    return (
        start.strftime("%Y-%m-%d %H:%M"),
        end.strftime("%Y-%m-%d %H:%M"),
    )


def anomalies(
    conn: sqlite3.Connection,
    period: str = "all"
) -> dict:

    latest_text = _latest_timestamp(conn)
    latest = datetime.fromisoformat(latest_text)

    start_at = None
    end_at = None

    if period == "week":
        start_at, end_at = _week_window(latest)

    elif period == "month":
        start_at, end_at = _month_window(latest)

    elif period != "all":
        raise ValueError(
            "period must be all, week, or month"
        )

    return {
        "period": period,
        "window_start": start_at,
        "window_end": end_at,
        "resolution_time_outliers": resolution_outliers(
            conn,
            start_at,
            end_at,
        ),
        "unresolved_high_priority_over_24h": unresolved_priority_old(
            conn,
            24.0,
            latest_text,
            start_at,
            end_at,
        ),
    }