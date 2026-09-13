"""
Benchmark solvability test: every claim labelled fraud must still contain every fraud signal
the generator designed into it (see app/synthetic/check_signals.py). No model calls.

Run from the backend/ folder:
    .\\.venv\\Scripts\\python.exe -m pytest tests -v
"""

from app.synthetic.check_signals import check_claim
from tests.test_sanitize import load_claims


def test_every_fraud_claim_still_contains_its_designed_signals():
    for raw_claim in load_claims():
        if not raw_claim["ground_truth"]["is_fraud"]:
            continue
        for signal, present, detail in check_claim(raw_claim):
            assert present, f"{raw_claim['claim_id']}: designed signal '{signal}' is missing ({detail})"
