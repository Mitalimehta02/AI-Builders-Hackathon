"""
System status for the frontend (Stage 8).

    GET /config   whether live claim submission is currently allowed, and why not if it isn't
"""

from fastapi import APIRouter

from app import batch_status

router = APIRouter(tags=["system"])


@router.get("/config")
def config():
    return batch_status.live_submission_state()
