from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from .anomaly import anomalies
from .config import STATIC_DIR
from .db import dataset_metadata, get_connection, initialize_database
from .llm import ollama_health
from .query import answer_question

TEMPLATES = Jinja2Templates(directory=str(STATIC_DIR.parent / "templates"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title="DOTMappers AI Support Ticket Analyst",
    description="LLM-powered natural-language analytics and anomaly detection over support tickets.",
    version="1.1.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def home(request: Request, question: str | None = None, period: str | None = None):
    context = {
        "request": request,
        "question": question or "",
        "query_result": None,
        "anomaly_result": None,
        "error": None,
    }

    conn = get_connection(read_only=True)
    try:
        if question and question.strip():
            context["query_result"] = answer_question(conn, question.strip())
        if period:
            context["anomaly_result"] = anomalies(conn, period=period)
    except Exception as exc:
        context["error"] = str(exc)
    finally:
        conn.close()

    return TEMPLATES.TemplateResponse(request=request, name="index.html", context=context)


@app.get("/api/health")
def health():
    metadata = dataset_metadata()
    return {"status": "ok", "dataset": metadata, "llm": ollama_health()}


@app.post("/api/query")
def query(request: QueryRequest):
    conn = get_connection(read_only=True)
    try:
        return answer_question(conn, request.question)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        conn.close()


@app.get("/api/anomalies")
def anomaly_report(period: str = "all"):
    if period not in {"all", "week", "month"}:
        raise HTTPException(
            status_code=400,
            detail="period must be one of: all, week, month",
        )

    conn = get_connection(read_only=True)
    try:
        return anomalies(conn, period=period)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        conn.close()
