# DOTMappers AI Engineer Assessment — AI Support Ticket Analyst

This project is my implementation of the DOTMappers AI Engineer assessment. It loads the supplied support-ticket CSV into SQLite, lets a user ask questions in normal language, detects ticket anomalies, and exposes the same functionality through a FastAPI REST API and a small web UI.

## Assessment requirements covered

- CSV ingestion and queryable storage
- Natural-language questions using a local LLM (Ollama)
- Read-only SQL generated from the question
- Resolution-time anomaly detection using IQR
- Unresolved High/Critical tickets older than 24 hours
- Time-aware anomaly checks for all data, this week, and this month
- REST API with health, NL query, and anomaly endpoints
- Minimal server-rendered UI served by FastAPI (no JavaScript framework)
- No paid API or external service is required
- One command to start the application after setup
- README and `requirements.txt`

The assessment asks for Python, an LLM, zero-cost/local execution, a single start command, and documentation. This implementation uses Python/FastAPI for the application and a server-rendered HTML page for the UI, with no JavaScript framework or frontend build step.

## Project structure

```text
.
├── app/
│   ├── anomaly.py       # anomaly calculations and time windows
│   ├── config.py        # paths and Ollama settings
│   ├── db.py            # CSV -> SQLite ingestion
│   ├── llm.py           # Ollama integration and prompt
│   ├── main.py          # FastAPI routes and web UI
│   └── query.py         # SQL validation, execution, and fallback
├── data/
│   └── support_tickets.csv
├── static/
│   └── style.css
├── templates/
│   └── index.html
├── tests/
│   └── test_api.py
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
 NL question -> SQL         IQR + age rule
        |
        v
  SQL safety checks
        |
        v
 SQLite read-only query
        |
        v
 JSON response / web page
```

### Design choices

**SQLite:** The supplied dataset is only 500 rows, so SQLite keeps the project simple and avoids a separate database server.

**Ollama:** It runs locally and does not need a paid API key. The default model is `llama3.2:3b`.

**LLM-to-SQL:** The LLM is used for natural-language understanding. It returns structured JSON containing SQL and an explanation. The generated SQL is checked before it reaches the database.

**Deterministic anomalies:** Statistical anomaly detection is handled in Python/SQLite rather than asking the LLM to decide whether a value is an anomaly. This makes the result repeatable.

**FastAPI:** It provides the required REST endpoints and also serves the small UI, so the whole application starts with one command.

## Dataset

The supplied CSV contains 500 rows and these columns:

- `ticket_id`
- `created_at`
- `category`
- `priority`
- `status`
- `response_time_hrs`
- `resolution_time_hrs`
- `agent_id`
- `customer_rating`
- `issue_summary`

`resolution_time_hrs` and `customer_rating` can be empty for unresolved tickets.

On startup the CSV is validated and loaded into `data/support_tickets.db`. The database file is ignored by Git and can be recreated at any time.

## Setup

### 1. Create a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 2b. (Optional) Configure environment variables

Copy the example file if you want to override any default (Ollama URL/model, timeout):

```bash
cp .env.example .env
```

This step is optional — the app works with its built-in defaults even without a `.env` file.

### 3. Install and start Ollama

Install Ollama locally and make sure its service is running.

Pull the default model:

```bash
ollama pull llama3.2:3b
```

If a different local model is preferred:

```text
OLLAMA_MODEL=<model-name>
```

The default Ollama address is:

```text
http://localhost:11434
```

### 4. Start the application

From the repository root:

```bash
uvicorn app.main:app --reload
```

Open the UI at:

```text
http://127.0.0.1:8000
```

API documentation:

```text
http://127.0.0.1:8000/docs
```

## REST API

### Health check

```http
GET /api/health
```

Shows API status, dataset row count/date range, and Ollama availability.

### Natural-language query

```http
POST /api/query
Content-Type: application/json

{
  "question": "How many tickets are currently open?"
}
```

The response contains the result rows, generated SQL, explanation, and whether the LLM was used.

### Anomaly detection

```http
GET /api/anomalies
GET /api/anomalies?period=week
GET /api/anomalies?period=month
```

The endpoint returns:

1. Resolution-time outliers using `Q3 + 1.5 * IQR`.
2. Unresolved High/Critical tickets older than 24 hours.

For `week` and `month`, the period is calculated relative to the latest timestamp in the supplied dataset. This avoids using the evaluator's current calendar date against a historical dataset.

## Example questions

The UI includes the assessment examples, including:

```text
How many tickets are currently open?
Which agent resolved the most tickets this month?
Show me all Critical tickets not resolved within 12 hours.
What is the average customer rating for Technical category tickets?
Are there any anomalies in resolution times this week?
```

Other questions the system can handle through the LLM include:

```text
How many Critical tickets are unresolved?
Which agent has the lowest average customer rating?
Show all Open Billing tickets.
What is the average response time for High priority tickets?
How many tickets were created in March 2024?
```

## Dataset validation values

These values were calculated from the supplied CSV and can be used to check a local installation:

| Check | Result |
|---|---:|
| Total tickets | 500 |
| Currently Open | 111 |
| Critical and not Resolved | 31 |
| Average Technical customer rating | 3.74 |
| Overall IQR resolution threshold | 48.15 hours |
| Overall resolution-time outliers | 21 |
| Most resolved tickets in March 2024 | AGT-01 (16) |

The supplied dataset's latest ticket timestamp is in March 2024. Therefore, phrases such as "this month" and "this week" are interpreted relative to the dataset, not the real-world date on which the application is run.

## LLM prompt and safety

The LLM receives the database schema and the dataset's latest timestamp. It is instructed to return only JSON with:

```json
{
  "sql": "SELECT ...",
  "explanation": "..."
}
```

Before execution, the application rejects:

- empty SQL
- multiple statements
- write operations such as INSERT/UPDATE/DELETE
- database administration commands
- queries that do not start with SELECT or WITH
- queries that do not reference `support_tickets`

API queries use a read-only SQLite connection.

If Ollama is unavailable, a small deterministic fallback is available for the assessment's common demonstration questions. This is only a resilience path; when Ollama is running, the normal natural-language query path uses the LLM.

## Running the sample walkthrough

After starting the application with Ollama running, test these assessment queries in the UI:

1. `How many tickets are currently open?`
2. `Which agent resolved the most tickets this month?`
3. `Show me all Critical tickets not resolved within 12 hours.`
4. `What is the average customer rating for Technical category tickets?`
5. `Are there any anomalies in resolution times this week?`

The UI also exposes links to `/docs` and the anomaly periods `all`, `week`, and `month`.

## Testing

Run:

```bash
pytest -q
```

The included tests cover:

- 500-row ingestion and health endpoint
- all-data and week-based anomaly endpoints
- the NL query endpoint without requiring Ollama during automated testing
- the server-rendered UI
- invalid anomaly-period and input validation responses

## Known limitations

- Natural-language accuracy depends on the local LLM model.
- Very ambiguous questions may need to be rephrased.
- The current database is designed for the supplied assessment dataset rather than large production workloads.
- Anomaly detection uses the dataset's latest timestamp as the reference point because the supplied data is historical.

## Assessment alignment

| Requirement | Implementation |
|---|---|
| CSV ingestion | `app/db.py` loads and validates the supplied CSV into SQLite |
| Natural-language questions | `app/llm.py` uses Ollama to translate questions into SQL |
| Anomaly detection | `app/anomaly.py` implements IQR outliers and unresolved High/Critical >24h |
| REST API | `/api/health`, `/api/query`, `/api/anomalies` |
| Minimal UI | Server-rendered HTML at `/` |
| LLM | Local Ollama, default `llama3.2:3b` |
| Zero-cost execution | No paid API or hosted service required |
| Single start command | `uvicorn app.main:app --reload` after setup |
| Documentation | This README |
| Dependencies | `requirements.txt` |

## Submission

1. Create a new public or recruiter-accessible GitHub repository.
2. Copy the project files into the repository.
3. Do **not** commit `.venv`, `data/support_tickets.db`, `.env`, or other local files ignored by `.gitignore`.
4. Run the tests and start the application locally before pushing.
5. Open the UI and test the sample questions with Ollama running.
6. Push the repository to GitHub.
7. Email the repository link to `RajathKumar@dotmappers.in`.
8. Use the subject line:

```text
[AI Engineer Assessment] — Atul Kumar
```

The assessment says a 30-minute architecture walkthrough will follow submission, so be ready to explain the choices above and what you would change for a larger production system.
