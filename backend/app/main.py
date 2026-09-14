"""
ClaimLens backend — FastAPI app entrypoint.

Run from the `backend/` folder with:
    .\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --reload

In production (see docs/DEPLOYMENT.md):
    uvicorn app.main:app --host 0.0.0.0 --port $PORT

Interactive API docs: http://localhost:8000/docs

Environment variables (all optional except GROQ_API_KEY for processing claims):
    GROQ_API_KEY                model access, needed only when a claim is actually processed
    CLAIMLENS_CORS_ORIGINS      comma-separated browser origins allowed to call the API directly
    CLAIMLENS_LIVE_SUBMISSION   "off" disables live claim submission (e.g. on the public demo)
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import db
from app.routes import analytics, claims, samples, system

# The frontend normally reaches this API through its own /api proxy, which needs no CORS. Origins
# listed here may also call the API directly from a browser.
CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CLAIMLENS_CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]


@asynccontextmanager
async def lifespan(app):
    db.init_db()  # create the SQLite table on startup
    yield


app = FastAPI(title="ClaimLens API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
app.include_router(claims.router)
app.include_router(samples.router)
app.include_router(system.router)
app.include_router(analytics.router)


@app.get("/health")
def health():
    """Simple check that the server is up and responding."""
    return {"status": "ok"}
