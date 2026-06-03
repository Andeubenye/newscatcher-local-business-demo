"""
core/catchall_client.py

All CatchAll API calls live here. Single responsibility:
talk to the CatchAll service and return raw responses.

Skill configuration lives in core/catchall_config.py.
Record normalization lives in core/normalize.py.
Client is lazy-initialised so the server starts without an API key
and only fails when an actual search request is made.
"""

import os
from dotenv import load_dotenv
from newscatcher_catchall import CatchAllApi
from newscatcher_catchall.core.api_error import ApiError

from core.catchall_config import SKILL_CONTEXT, VALIDATORS, ENRICHMENTS

load_dotenv()

# Lazy-init pattern — module imports without a key, fails only at first use
_client = None


def _get_client() -> CatchAllApi:
    """Return the singleton CatchAll client, creating it on first call."""
    global _client
    if _client is None:
        api_key = os.environ.get("CATCHALL_API_KEY")
        if not api_key:
            raise RuntimeError(
                "CATCHALL_API_KEY is missing. Add it to your .env file."
            )
        _client = CatchAllApi(api_key=api_key)
    return _client


def _to_dict(obj) -> dict:
    """Coerce SDK response objects into plain dicts for JSON serialization."""
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "dict"):
        return obj.dict()
    try:
        return vars(obj)
    except TypeError:
        return {}


def initialize(query: str) -> dict:
    """Free preview — no credits spent. Returns date warnings if applicable."""
    try:
        return _to_dict(_get_client().jobs.initialize(
            query=query,
            context=SKILL_CONTEXT,
        ))
    except ApiError as e:
        raise RuntimeError(f"initialize failed [{e.status_code}]: {e.body}") from e


def submit(query: str, limit: int = 50) -> str:
    """Create a job (credits spent here). Returns the job_id immediately."""
    try:
        response = _get_client().jobs.create_job(
            query=query,
            context=SKILL_CONTEXT,
            validators=VALIDATORS,
            enrichments=ENRICHMENTS,
            limit=limit,
            mode="base",
        )
        return response.job_id
    except ApiError as e:
        raise RuntimeError(f"submit failed [{e.status_code}]: {e.body}") from e


def get_status(job_id: str) -> dict:
    """Poll job status. States: analyzing → fetching → enriching → completed/failed."""
    try:
        return _to_dict(_get_client().jobs.get_job_status(job_id=job_id))
    except ApiError as e:
        raise RuntimeError(f"get_status failed [{e.status_code}]: {e.body}") from e


def pull_all(job_id: str) -> list:
    """Pull all paginated results. Returns a flat list of raw record dicts."""
    all_records = []
    page = 1

    while True:
        try:
            response = _to_dict(_get_client().jobs.get_job_results(
                job_id=job_id,
                page=page,
                page_size=100,
            ))
            all_records.extend(response.get("all_records", []))

            if page >= response.get("total_pages", 1):
                break
            page += 1

        except ApiError as e:
            raise RuntimeError(f"pull_all failed [{e.status_code}]: {e.body}") from e

    return all_records


def create_monitor(job_id: str, schedule: str = "every day at 8 AM UTC") -> str:
    """Turn a completed job into a daily recurring search. Returns the monitor_id."""
    try:
        response = _get_client().monitors.create_monitor(
            reference_job_id=job_id,
            schedule=schedule,
            backfill=True,
        )
        return response.monitor_id
    except ApiError as e:
        raise RuntimeError(f"create_monitor failed [{e.status_code}]: {e.body}") from e
