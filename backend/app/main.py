"""
ClaimLens backend — FastAPI app entrypoint.

Run from the `backend/` folder with:
    uvicorn app.main:app --reload

Stage 1 only has a health check. Claim and analytics routes get added in later stages.
"""

from fastapi import FastAPI

app = FastAPI(title="ClaimLens API")


@app.get("/health")
def health():
    """Simple check that the server is up and responding."""
    return {"status": "ok"}
