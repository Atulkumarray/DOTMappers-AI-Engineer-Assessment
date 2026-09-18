import json
import re

import requests

from .config import OLLAMA_BASE_URL, OLLAMA_MODEL, LLM_TIMEOUT_SECONDS

SCHEMA = """
Table: support_tickets
Columns:
- ticket_id TEXT: unique ticket identifier
- created_at TEXT: timestamp, format YYYY-MM-DD HH:MM
- category TEXT: Billing | Technical | General
- priority TEXT: Low | Medium | High | Critical
- status TEXT: Open | Resolved | Escalated
- response_time_hrs REAL: hours to first response
- resolution_time_hrs REAL: hours to resolution; NULL when unresolved
- agent_id TEXT: assigned agent identifier
- customer_rating REAL: 1-5; NULL when unresolved
- issue_summary TEXT: free-text issue summary
"""


def build_system_prompt(latest_created_at: str) -> str:
    return f"""
You translate customer-support questions into safe, read-only SQLite SQL.

{SCHEMA}

The latest ticket in this dataset was created at: {latest_created_at}

Rules:
1. Return ONLY valid JSON with keys: "sql" and "explanation".
2. SQL must be a single read-only SELECT query. CTEs (WITH ... SELECT) are allowed.
3. Never use INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, ATTACH, DETACH, PRAGMA, REPLACE, VACUUM, REINDEX, or multiple statements.
4. Use only the support_tickets table and its columns.
5. Relative periods must use the dataset's latest timestamp above, not today's real-world date.
   - "this month" means the calendar month containing the latest dataset timestamp.
   - "this week" means the Monday-Sunday week containing the latest dataset timestamp.
6. "Unresolved" means status != 'Resolved' unless the user clearly specifies another condition.
7. For averages/counts, return a compact result with useful aliases.
8. For "show/list" requests, return the requested ticket fields and order results sensibly.
9. Ignore NULL customer_rating values when calculating averages.
10. Do not invent columns or values.
11. SQL must be compatible with SQLite.
12. For date filtering, use SQLite datetime()/date() functions and ISO timestamps.
"""


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError("LLM did not return JSON")
    result = json.loads(match.group(0))
    if not isinstance(result, dict) or "sql" not in result:
        raise ValueError("Invalid LLM response structure")
    return result


def generate_sql(question: str, latest_created_at: str) -> dict:
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": build_system_prompt(latest_created_at)},
            {"role": "user", "content": question},
        ],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0},
    }
    response = requests.post(
        f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat",
        json=payload,
        timeout=LLM_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return _extract_json(response.json()["message"]["content"])


def ollama_health() -> dict:
    try:
        r = requests.get(f"{OLLAMA_BASE_URL.rstrip('/')}/api/tags", timeout=5)
        if r.ok:
            models = [m.get("name") for m in r.json().get("models", [])]
            return {"available": True, "models": models, "configured_model": OLLAMA_MODEL}
    except requests.RequestException:
        pass
    return {"available": False, "models": [], "configured_model": OLLAMA_MODEL}
