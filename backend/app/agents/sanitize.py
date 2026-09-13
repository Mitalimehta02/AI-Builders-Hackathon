"""
The ONE place that removes the answer sheet from a claim before any agent sees it.

Synthetic claims carry a "ground_truth" block (is_fraud, difficulty, signals). If any of
that reaches an agent or a prompt, every accuracy number in Stage 11 is worthless. So:

- Every agent (evidence, baseline, debate, calibration) must receive sanitize_claim(claim),
  never the raw claim.
- Agents can call find_label_keys() to refuse input that still carries label keys.
"""

# Keys that hold the ground-truth label or anything derived from it. They are removed
# wherever they appear in the claim, not just at the top level.
LABEL_KEYS = {"ground_truth", "is_fraud", "difficulty", "signals"}


def sanitize_claim(claim):
    """Return a copy of the claim with all label keys removed. The original is not modified."""
    return _strip_label_keys(claim)


def _strip_label_keys(value):
    if isinstance(value, dict):
        return {key: _strip_label_keys(item) for key, item in value.items() if key not in LABEL_KEYS}
    if isinstance(value, list):
        return [_strip_label_keys(item) for item in value]
    return value


def find_label_keys(value, path="claim"):
    """Return the paths of any label keys still present, e.g. ["claim.ground_truth"].
    An empty list means the object is clean."""
    found = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in LABEL_KEYS:
                found.append(f"{path}.{key}")
            found += find_label_keys(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found += find_label_keys(item, f"{path}[{index}]")
    return found
