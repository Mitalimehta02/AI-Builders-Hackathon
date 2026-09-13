"""
Stage 3 check: run the evidence agent on three hand-picked claims and print the results.

  CLM-0035  fraud: a "frozen pipe" in Miami in July (weather mismatch)
  CLM-0027  legitimate, but with innocent look-alike flags (brand-new policy + prior claims)
  CLM-0001  an ambiguous case

For CLM-0035 it also prints the raw Open-Meteo response, so you can see the external call
is real. Run from the backend/ folder:
    .\\.venv\\Scripts\\python.exe -m app.synthetic.test_evidence
"""

import json
from pathlib import Path

from app.agents.evidence_agent import gather_evidence
from app.agents.sanitize import sanitize_claim
from app.tools.weather_tool import get_historical_weather

CLAIMS_PATH = Path(__file__).resolve().parents[2] / "data" / "synthetic_claims.json"
SAMPLE_CLAIM_IDS = ["CLM-0035", "CLM-0027", "CLM-0001"]
SHOW_RAW_WEATHER_FOR = "CLM-0035"


def main():
    with open(CLAIMS_PATH, encoding="utf-8") as f:
        claims_by_id = {c["claim_id"]: c for c in json.load(f)}

    for claim_id in SAMPLE_CLAIM_IDS:
        raw_claim = claims_by_id[claim_id]

        # Keep the raw weather result so we can show exactly what the API returned.
        weather_results = []

        def recording_weather_lookup(latitude, longitude, start_date, end_date):
            result = get_historical_weather(latitude, longitude, start_date, end_date)
            weather_results.append(result)
            return result

        evidence = gather_evidence(sanitize_claim(raw_claim), weather_lookup=recording_weather_lookup)

        truth = raw_claim["ground_truth"]
        print("=" * 78)
        print(f"{claim_id}  ({raw_claim['claim_type']}, ${raw_claim['claim_amount']:,.2f})")
        print(f"Answer, for YOUR reference only (never given to the agent): "
              f"is_fraud={truth['is_fraud']}, difficulty={truth['difficulty']}, signals={truth['signals']}")
        print(f"Description: {raw_claim['incident']['description']}")
        print("-" * 78)
        print("EVIDENCE OBJECT:")
        print(json.dumps(evidence, indent=2))

        if claim_id == SHOW_RAW_WEATHER_FOR and weather_results:
            result = weather_results[0]
            print("-" * 78)
            print("RAW OPEN-METEO RESULT:")
            if result["status"] == "ok":
                print(f"  served from: {'local cache (fetched earlier)' if result['from_cache'] else 'LIVE API call just now'}")
                print(f"  fetched_at:  {result['fetched_at']}")
                print(f"  request_url: {result['request_url']}")
                print(json.dumps(result["response"], indent=2))
            else:
                print(f"  unavailable: {result['reason']}")

    print("=" * 78)
    print(f"Evidence JSON size per claim (characters): "
          + ", ".join(f"{cid}={len(json.dumps(gather_evidence(sanitize_claim(claims_by_id[cid]))))}" for cid in SAMPLE_CLAIM_IDS))


if __name__ == "__main__":
    main()
