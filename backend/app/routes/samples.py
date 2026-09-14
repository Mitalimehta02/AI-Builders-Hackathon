"""
Stored sample results (Stage 8). Zero model calls: everything here is read from files.

    GET /samples             stored development-set results available to load on the intake page
    GET /samples/{claim_id}  one stored result, in the same shape as GET /claims/{id}
"""

from fastapi import APIRouter, HTTPException

from app import samples

router = APIRouter(prefix="/samples", tags=["samples"])


@router.get("")
def list_samples():
    return samples.list_samples()


@router.get("/{claim_id}")
def sample_detail(claim_id: str):
    detail = samples.get_sample(claim_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"no stored sample for {claim_id}")
    return detail
