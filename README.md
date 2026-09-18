# DOTMappers AI Engineer Assessment — AI Support Ticket Analyst

This project is my implementation of the **DOTMappers AI Engineer Assessment — AI Support Ticket Analyst**.

The application loads the supplied support-ticket CSV into SQLite, allows users to ask questions in natural language, converts questions into safe read-only SQL using a local LLM, detects resolution-time anomalies, identifies unresolved High/Critical tickets older than 24 hours, and exposes the functionality through a FastAPI REST API and a minimal web UI.

## Assessment Requirements Covered

* CSV ingestion and queryable storage
* Natural-language questions using a local LLM
* Ollama-based local LLM execution
* Read-only SQL generation and validation
* Resolution-time anomaly detection using IQR
* Detection of unresolved High/Critical tickets older than 24 hours
* Time-aware anomaly detection for all data, this week, and this month
* REST API with health, NL query, and anomaly endpoints
* Minimal server-rendered HTML UI
* No JavaScript framework or frontend build step
* No paid API or external AI service required
* SQLite database for simple local execution
* One command to start the application
* Automated tests
* README and requirements.txt documentation

## Project Structure

```text
.
├── app/
│   ├── anomaly.py       # Anomaly calculations and time windows
│   ├── config.py        # Application and Ollama configuration
│   ├── db.py            # CSV validation and SQLite ingestion
│   ├── llm.py           # Ollama integration and LLM prompt
│   ├── main.py          # FastAPI routes and web UI
│   └── query.py         # SQL validation, execution and fallback
│
├── data/
│   └── support_tickets.csv
│
├── static/
│   └── style.css
│
├── templates/
│   └── index.html
│
├── tests/
│   └── test_api.py
│
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## Architecture

```text
support_tickets.csv
        |
        v
 CSV validation / ingestion
        |
        v
      SQLite
        |
        +-------------------------+
        |                         |
        v                         v
 POST /api/query            GET /api/anomalies
        |                         |
        v                         v
   Ollama LLM              Python anomaly logic
        |                    IQR + age rule
        v
 NL question -> SQL
        |
        v
 SQL safety validation
        |
        v
 Read-only SQLite query
        |
        v
 JSON response / Web UI
```

## Technology Stack

### Backend

* Python
* FastAPI
* Uvicorn
* SQLite

### AI / LLM

* Ollama
* Default model: `llama3.2:3b`

### Data Processing

* CSV
* SQLite
* IQR-based anomaly detection

### Frontend

* HTML
* CSS
* Server-rendered FastAPI templates

### Testing

* Pytest

## Design Decisions

### SQLite

The supplied dataset contains only 500 tickets, so SQLite is sufficient and keeps the application lightweight. It also avoids requiring a separate database server.

### Ollama

Ollama provides local LLM execution without requiring a paid API key or external AI service.

The default model is:

```text
llama3.2:3b
```

The model can be changed using the `OLLAMA_MODEL` environment variable.

### LLM-to-SQL

The LLM is responsible for understanding the user's natural-language question and generating SQL.

The expected LLM response is structured JSON:

```json
{
  "sql": "SELECT ...",
  "explanation": "..."
}
```

The generated SQL is validated before execution.

The LLM is not responsible for determining statistical anomalies. Anomaly detection is handled deterministically by Python/SQLite so that the results are repeatable.

### FastAPI

FastAPI provides both the REST API and the web interface. This keeps the entire application in one Python service and allows it to be started with a single command.

## Dataset

The supplied CSV contains **500 support tickets** with the following columns:

* `ticket_id`
* `created_at`
* `category`
* `priority`
* `status`
* `response_time_hrs`
* `resolution_time_hrs`
* `agent_id`
* `customer_rating`
* `issue_summary`

`resolution_time_hrs` and `customer_rating` can be empty for unresolved tickets.

On application startup, the CSV is validated and loaded into:

```text
data/support_tickets.db
```

The SQLite database is ignored by Git and can be recreated from the CSV.

## Setup

### 1. Create a Virtual Environment

#### Windows PowerShell

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

#### macOS/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Environment variables are optional.

You can copy the example configuration:

```bash
cp .env.example .env
```

The application has built-in defaults, so the `.env` file is not required.

Example:

```text
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b
OLLAMA_TIMEOUT=60
```

### 4. Install Ollama

Install Ollama locally and make sure the Ollama service is running.

Pull the default model:

```bash
ollama pull llama3.2:3b
```

The default Ollama URL is:

```text
http://localhost:11434
```

### 5. Start the Application

From the repository root:

```bash
uvicorn app.main:app --reload
```

Open the web application at:

```text
http://127.0.0.1:8000
```

FastAPI Swagger documentation:

```text
http://127.0.0.1:8000/docs
```

## REST API

### Health Check

```http
GET /api/health
```

Returns:

* API status
* Dataset row count
* Dataset date range
* Ollama availability

### Natural-Language Query

```http
POST /api/query
Content-Type: application/json
```

Example request:

```json
{
  "question": "How many tickets are currently open?"
}
```

The response contains:

* Query result rows
* Generated SQL
* Explanation
* Whether the LLM was used

### Anomaly Detection

All data:

```http
GET /api/anomalies
```

This week:

```http
GET /api/anomalies?period=week
```

This month:

```http
GET /api/anomalies?period=month
```

The anomaly endpoint checks:

1. Resolution-time outliers using the IQR method.
2. Unresolved High/Critical tickets older than 24 hours.

For `week` and `month`, the application calculates the period relative to the **latest timestamp in the supplied dataset**.

This is important because the supplied dataset is historical and should not be compared against the evaluator's current calendar date.

## Anomaly Detection

Resolution-time anomalies are calculated using the standard IQR rule:

```text
IQR = Q3 - Q1

Upper threshold = Q3 + 1.5 × IQR
```

Tickets with resolution times above the upper threshold are considered resolution-time outliers.

The application also identifies tickets that satisfy:

```text
priority = High OR Critical
AND
status != Resolved
AND
age > 24 hours
```

The anomaly calculations are deterministic and do not depend on the LLM.

## Example Questions

The web UI includes the assessment's example questions:

```text
How many tickets are currently open?
```

```text
Which agent resolved the most tickets this month?
```

```text
Show me all Critical tickets not resolved within 12 hours.
```

```text
What is the average customer rating for Technical category tickets?
```

```text
Are there any anomalies in resolution times this week?
```

Additional supported questions include:

```text
How many Critical tickets are unresolved?
```

```text
Which agent has the lowest average customer rating?
```

```text
Show all Open Billing tickets.
```

```text
What is the average response time for High priority tickets?
```

```text
How many tickets were created in March 2024?
```

## Dataset Validation Results

The following values were calculated from the supplied CSV and can be used to verify the application:

| Check                               |      Result |
| ----------------------------------- | ----------: |
| Total tickets                       |         500 |
| Currently Open                      |         111 |
| Critical and not Resolved           |          31 |
| Average Technical customer rating   |        3.74 |
| Overall IQR resolution threshold    | 48.15 hours |
| Overall resolution-time outliers    |          21 |
| Most resolved tickets in March 2024 | AGT-01 (16) |

The latest ticket timestamp in the supplied dataset is in **March 2024**.

Therefore, phrases such as:

```text
this week
```

and

```text
this month
```

are interpreted relative to the dataset's latest timestamp rather than the real-world date on which the application is executed.

## LLM Prompt and SQL Safety

The LLM receives:

* Database schema
* Column information
* Dataset's latest timestamp
* User's natural-language question

It is instructed to return only structured JSON containing SQL and an explanation.

Before SQL execution, the application validates the generated query.

The following are rejected:

* Empty SQL
* Multiple SQL statements
* `INSERT`
* `UPDATE`
* `DELETE`
* `DROP`
* `ALTER`
* `CREATE`
* `TRUNCATE`
* Database administration commands
* Queries that do not begin with `SELECT` or `WITH`
* Queries that do not reference `support_tickets`

API queries use a read-only SQLite connection to prevent accidental data modification.

## Fallback Query Handling

If Ollama is unavailable, the application provides a small deterministic fallback for common assessment demonstration questions.

This fallback is only a resilience mechanism.

When Ollama is available, normal natural-language questions are processed through the local LLM.

## Running the Assessment Walkthrough

After starting the application and ensuring Ollama is running, test the following questions:

### 1. Open Tickets

```text
How many tickets are currently open?
```

### 2. Top Agent

```text
Which agent resolved the most tickets this month?
```

### 3. Critical Tickets

```text
Show me all Critical tickets not resolved within 12 hours.
```

### 4. Technical Rating

```text
What is the average customer rating for Technical category tickets?
```

### 5. Resolution Anomalies

```text
Are there any anomalies in resolution times this week?
```

The UI also provides access to:

```text
/api/health
/api/query
/api/anomalies
```

and the FastAPI documentation at:

```text
/docs
```

## Testing

Run the automated test suite:

```bash
pytest -q
```

The tests cover:

* 500-row CSV ingestion
* Health endpoint
* Dataset validation
* All-data anomaly detection
* Week-based anomaly detection
* Natural-language query endpoint
* Server-rendered web UI
* Invalid anomaly period handling
* Input validation
* Query execution without requiring Ollama during automated tests

## One-Command Start

After the initial setup and Ollama model installation, the application can be started with:

```bash
uvicorn app.main:app --reload
```

This starts both the REST API and the web UI.

## API Documentation

FastAPI automatically provides interactive API documentation at:

```text
http://127.0.0.1:8000/docs
```

The alternative ReDoc documentation is available at:

```text
http://127.0.0.1:8000/redoc
```

## Known Limitations

* Natural-language query accuracy depends on the selected local LLM.
* Highly ambiguous questions may require rephrasing.
* The SQLite implementation is intended for the supplied assessment dataset rather than large production workloads.
* The supplied dataset is historical, so relative periods use the dataset's latest timestamp.
* Ollama must be installed locally for full LLM functionality.
* The fallback query system only covers a limited set of common demonstration questions.

## Summary

This implementation combines:

```text
Python
   +
FastAPI
   +
SQLite
   +
Ollama
   +
Natural Language → Safe SQL
   +
Deterministic IQR Anomaly Detection
   +
Server-rendered Web UI
```

The project is designed to satisfy the assessment requirements while remaining **local, zero-cost, lightweight, testable, and easy to run**.
