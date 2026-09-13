"""
ClaimLens backend — FastAPI app entrypoint.

Run from the `backend/` folder with:
    .\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --reload

Interactive API docs: http://localhost:8000/docs
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import db
from app.routes import claims


@asynccontextmanager
async def lifespan(app):
    db.init_db()  # create the SQLite table on startup
    yield


app = FastAPI(title="ClaimLens API", lifespan=lifespan)
app.include_router(claims.router)


@app.get("/health")
def health():
    """Simple check that the server is up and responding."""
    return {"status": "ok"}
