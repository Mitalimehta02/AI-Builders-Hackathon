"""
Processing one submitted claim (Stage 7): the work POST /claims starts in the background.

    pending -> gathering_evidence -> debating -> calibrating -> resolved
                                                       (or failed, with the error stored)

It runs exactly the Stage 3, 5 and 6 code used by the evaluation scripts: gather_evidence, then
run_claimlens (Prosecutor, Defender, Prosecutor rebuttal, Judge, order-swapped Judge, confidence
tier, rebuttal-accounting cap, auto-resolution gate), all through the shared model client.

Each debate step is saved to the database as soon as it finishes, so the status endpoint can
show progress, and a claim that fails part-way keeps the model output it already paid for.
"""

from app import db
from app.agents.calibration import run_claimlens
from app.agents.evidence_agent import gather_evidence
from app.agents.llm_client import call_llm
from app.models import CALIBRATING, DEBATING, FAILED, GATHERING_EVIDENCE, RESOLVED
from app.tools.weather_tool import get_historical_weather


def process_claim(record_id):
    """Run the full ClaimLens pipeline for one stored claim, recording progress as it goes."""
    record = db.get_claim(record_id)
    claim = record["claim"]
    try:
        db.update_claim(record_id, status=GATHERING_EVIDENCE)
        evidence = gather_evidence(claim, weather_lookup=get_historical_weather)
        db.update_claim(record_id, status=DEBATING, evidence=evidence)

        def save_step(steps):
            # Once the first Judge has ruled, what remains is the calibration step.
            db.update_claim(record_id, status=CALIBRATING if "judge" in steps else DEBATING, steps=steps)

        result = run_claimlens(claim, evidence, llm=call_llm, completed_steps=record["steps"], on_step=save_step)
        db.update_claim(record_id, status=RESOLVED, result=result, error=None)
    except Exception as error:  # record every failure on the claim itself, not only in a server log
        db.update_claim(record_id, status=FAILED, error=f"{error.__class__.__name__}: {error}")
