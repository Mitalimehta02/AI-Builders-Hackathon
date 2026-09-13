"""
Data models for the API (Stage 7).

ClaimSubmission mirrors the claim format produced by the Stage 2 generator, which is also the
format every agent reads. FastAPI checks each submitted claim against it and answers with a 422
error naming any missing or malformed field. Fields the model doesn't define - including a
synthetic claim's "ground_truth" answer sheet - are dropped and never stored.
"""

import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

# Processing statuses, in the order a claim moves through them.
# "failed" means processing stopped with an error; the error is stored with the claim.
PENDING = "pending"
GATHERING_EVIDENCE = "gathering_evidence"
DEBATING = "debating"
CALIBRATING = "calibrating"
RESOLVED = "resolved"
FAILED = "failed"
STATUSES = (PENDING, GATHERING_EVIDENCE, DEBATING, CALIBRATING, RESOLVED, FAILED)
FINISHED_STATUSES = (RESOLVED, FAILED)


class Address(BaseModel):
    street: str
    city: str
    state: str


class IncidentLocation(Address):
    # Coordinates are optional; without them the weather check is recorded as unavailable.
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class Policyholder(BaseModel):
    # Personal identifiers are optional and never shown to the agents (see case_file.py).
    name: str | None = None
    date_of_birth: datetime.date | None = None
    phone: str | None = None
    email: str | None = None
    address: Address


class InsuredVehicle(BaseModel):
    year: int = Field(ge=1950, le=2100)
    make: str
    model: str
    license_plate: str | None = None
    estimated_value: float = Field(gt=0)


class InsuredProperty(Address):
    property_type: str
    year_built: int = Field(ge=1700, le=2100)


class PolicyChange(BaseModel):
    date: datetime.date
    change: str


class Policy(BaseModel):
    policy_number: str
    policy_type: str
    start_date: datetime.date
    deductible: float = Field(ge=0)
    coverage_history: list[PolicyChange] = []
    # Auto policies
    coverages: list[str] | None = None
    insured_vehicle: InsuredVehicle | None = None
    # Property policies
    insured_property: InsuredProperty | None = None
    dwelling_coverage: float | None = Field(default=None, gt=0)
    contents_coverage: float | None = Field(default=None, gt=0)


class Incident(BaseModel):
    date: datetime.date
    location: IncidentLocation
    description: str = Field(min_length=1)
    damage: str = Field(min_length=1)


class PriorClaim(BaseModel):
    date: datetime.date
    claim_type: Literal["auto", "property"]
    summary: str
    amount: float = Field(ge=0)
    status: str
    insurer: str


class ClaimSubmission(BaseModel):
    """A claim as submitted to POST /claims."""

    claim_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9-]{1,40}$")
    claim_type: Literal["auto", "property"]
    filed_date: datetime.date
    policyholder: Policyholder
    policy: Policy
    incident: Incident
    claim_amount: float = Field(gt=0)
    supporting_documents: list[str] = []
    prior_claims: list[PriorClaim] = []

    @model_validator(mode="after")
    def check_claim_is_consistent(self):
        if self.claim_type == "auto" and (self.policy.insured_vehicle is None or not self.policy.coverages):
            raise ValueError("auto claims need policy.insured_vehicle and policy.coverages")
        if self.claim_type == "property" and (
            self.policy.insured_property is None
            or self.policy.dwelling_coverage is None
            or self.policy.contents_coverage is None
        ):
            raise ValueError("property claims need policy.insured_property, policy.dwelling_coverage and policy.contents_coverage")
        if not self.policy.start_date <= self.incident.date <= self.filed_date:
            raise ValueError("dates must satisfy policy.start_date <= incident.date <= filed_date")
        return self

    def to_claim_dict(self):
        """The claim in the plain format the agents read: dates as YYYY-MM-DD, empty optional fields left out."""
        return self.model_dump(mode="json", exclude_none=True)
