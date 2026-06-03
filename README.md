# Hyperlocal Business Intel — Backend

Demo-ready FastAPI backend for the Hyperlocal Business Intel demo.
Powered by CatchAll Web Search API.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Add your CATCHALL_API_KEY — everything else is optional
uvicorn api:app --reload --port 8000
```

## Routes

| Method | Route | Description |
|--------|-------|-------------|
| POST | /api/search | Submit first query, return job_id + remaining |
| POST | /api/next | Submit next query after previous completes |
| GET | /api/status/{job_id} | Poll job progress |
| GET | /api/results/{job_id} | Pull normalized results |
| POST | /api/monitor | Create daily monitor |


## Data storage

The demo uses CatchAll job results plus browser `localStorage` for saved datasets. No Supabase database is required for the Railway demo.
