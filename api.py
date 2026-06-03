"""
api.py — Hyperlocal Business Intel — Demo Backend

FastAPI app exposing CatchAll-powered routes for the demo frontend.

Sequential job design: one CatchAll job at a time to respect the
plan's concurrency limit of 1. The frontend submits the first query
via /api/search, then chains subsequent queries via /api/next after
each job completes. Results render progressively.

Start:
    uvicorn api:app --reload --port 8000 (or available port)
"""

import os
from typing import Optional

import requests
from core.email_client import send_digest
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from core.catchall_client import (
    initialize, submit, get_status, pull_all, create_monitor,
)
from core.normalize import normalize_record, deduplicate
from intel import build_opening_intel_with_ai, chat_with_opening_records

load_dotenv()

app = FastAPI(title="Hyperlocal Business Intel", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Signal terms run sequentially to broaden recall while respecting concurrency
SIGNAL_TERMS = ["grand opening", "now open", "soft opening"]
DEFAULT_JOB_LIMIT = 50


# ──────────────────────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    business_type: str
    city:          str
    country:       str
    street:        Optional[str] = ""
    days:          int = Field(default=14, ge=1, le=30)


class NextRequest(BaseModel):
    query: str


class MonitorRequest(BaseModel):
    job_id:   str
    schedule: Optional[str] = "every day at 8 AM UTC"


class IntelRequest(BaseModel):
    results:    list
    user_query: Optional[str] = None


class ChatRequest(BaseModel):
    results:    list
    user_query: str


class EmailResultsRequest(BaseModel):
    email: str
    results: list
    query: Optional[str] = None


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def _build_location(street: str, city: str, country: str) -> str:
    """Join street, city, country into a single location string."""
    if street:
        return f"{street}, {city}, {country}"
    return f"{city}, {country}"


def _build_queries(business_type: str, location: str, days: int) -> list:
    """Build one query per signal term."""
    return [
        f"{signal} {business_type} {location} last {days} days"
        for signal in SIGNAL_TERMS
    ]


def _extract_date_warning(preview: dict) -> Optional[str]:
    """Pull the first date modification message from a preview response."""
    msgs = preview.get("date_modification_message")
    if not msgs:
        return None
    return msgs[0] if isinstance(msgs, list) else msgs


# ──────────────────────────────────────────────────────────────
# Pages
# ──────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
def serve_index():
    return FileResponse("index.html")


@app.get("/dashboard", include_in_schema=False)
def serve_dashboard():
    return FileResponse("dashboard.html")


# ──────────────────────────────────────────────────────────────
# Health
# ──────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok"}


# ──────────────────────────────────────────────────────────────
# Search flow — sequential job submission
# ──────────────────────────────────────────────────────────────

@app.post("/api/search")
def api_search(body: SearchRequest):
    """Submit the FIRST signal-term job. Return job_id + remaining queries."""
    location = _build_location(body.street, body.city, body.country)
    queries = _build_queries(body.business_type, location, body.days)

    try:
        preview = initialize(query=queries[0])
        date_warning = _extract_date_warning(preview)
        job_id = submit(query=queries[0], limit=DEFAULT_JOB_LIMIT)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return {
        "job_id":       job_id,
        "query":        queries[0],
        "remaining":    queries[1:],
        "location":     location,
        "date_warning": date_warning,
    }


@app.post("/api/next")
def api_next(body: NextRequest):
    """Submit the next query after the previous job completes."""
    try:
        job_id = submit(query=body.query, limit=DEFAULT_JOB_LIMIT)
        return {"job_id": job_id, "query": body.query}
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/status/{job_id}")
def api_status(job_id: str):
    try:
        return get_status(job_id)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/results/{job_id}")
def api_results(job_id: str):
    """Pull, normalize, and deduplicate all records for a job."""
    try:
        raw = pull_all(job_id)
        normalized = [normalize_record(r) for r in raw]
        deduplicated = deduplicate(normalized)
        return {
            "job_id":  job_id,
            "total":   len(deduplicated),
            "results": deduplicated,
        }
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/api/results/{job_id}/email")
def api_email_results(job_id: str, body: EmailResultsRequest):
    """Send selected records to the recipient supplied by the dashboard."""
    if not body.email or "@" not in body.email:
        raise HTTPException(status_code=400, detail="Enter a valid email recipient.")
    if not body.results:
        raise HTTPException(status_code=400, detail="No records selected for email export.")

    ok = send_digest(body.email, body.results, body.query or f"CatchAll job {job_id}")
    if not ok:
        raise HTTPException(status_code=503, detail="Email could not be sent. Check Gmail settings.")
    return {"emailed": True, "recipient": body.email, "count": len(body.results)}


# ──────────────────────────────────────────────────────────────
# Monitor
# ──────────────────────────────────────────────────────────────

@app.post("/api/monitor")
def api_monitor(body: MonitorRequest):
    try:
        monitor_id = create_monitor(job_id=body.job_id, schedule=body.schedule)
        return {"monitor_id": monitor_id}
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))



# ──────────────────────────────────────────────────────────────
# Intel — deterministic + optional AI readout
# ──────────────────────────────────────────────────────────────

@app.post("/api/intel")
async def api_intel(body: IntelRequest):
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")
    return await build_opening_intel_with_ai(
        body.results,
        user_query=body.user_query or None,
        openrouter_api_key=openrouter_key,
    )


@app.post("/api/chat")
async def api_chat(body: ChatRequest):
    """Chat with the dataset. Falls back to deterministic readout without OpenRouter."""
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")
    return await chat_with_opening_records(
        body.results,
        body.user_query,
        openrouter_api_key=openrouter_key,
    )


# ──────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
