"""
Shared Groq client (Stage 4). EVERY model call in ClaimLens goes through call_llm().

Why one helper:
- Identical model and generation settings at every call site. This is the HONESTY RULE in
  PROJECT_PLAN.md Part 6: the naive baseline and the full pipeline must use the same model
  with the same settings, so the Stage 11 comparison measures architecture, nothing else.
- One place that handles rate limits (HTTP 429) and transient errors with capped backoff,
  and paces requests so we wait for the per-minute token window instead of hitting it.
- Every attempt, successful or not, is appended to backend/data/llm_logs/<UTC date>.jsonl
  with the full request, the full raw response, token counts and a timestamp. Quota is
  finite: we should never have to re-spend a call just to see what the model said.

API key: read from the GROQ_API_KEY environment variable. backend/.env is loaded first, but
a GROQ_API_KEY already set in the operating system environment takes precedence over .env.

Usage:
    from app.agents.llm_client import call_llm
    result = call_llm(messages, label="naive_baseline:CLM-0035")
    result["data"]        # the parsed JSON object the model returned
    result["usage"]       # tokens used, summed over every attempt that got a response
    result["attempts"]    # requests sent (each one counts against the daily request quota)
    result["rate_limit"]  # Groq's rate-limit headers from the final response
"""

import json
import os
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import groq
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = BACKEND_DIR / ".env"
LOG_DIR = BACKEND_DIR / "data" / "llm_logs"

# ---------------------------------------------------------------------------
# Model and generation settings. Fixed HERE, used by EVERY call. Never override per call.
# ---------------------------------------------------------------------------
# Fallback per PROJECT_PLAN.md is "llama-3.3-70b-versatile" - if you ever switch, switch it
# here so the baseline and the pipeline change together (and drop reasoning_effort, which
# only reasoning models accept).
MODEL = "openai/gpt-oss-120b"

GENERATION_SETTINGS = {
    # 0.2: low-variance sampling. Lowered from 1.0 before the Stage 11 run (no held-out claim had
    # been run): at 1.0 a dev claim changed decision between runs, so the order-swap check could not
    # tell genuine order-sensitivity from sampling noise. See docs/METHODOLOGY.md.
    "temperature": 0.2,
    # gpt-oss is a reasoning model. "medium" leaves room to weigh evidence properly while
    # keeping reasoning tokens (which count against quota) under control.
    "reasoning_effort": "medium",
    # Hard cap on output tokens (reasoning + answer) so one runaway reply can't drain quota.
    "max_completion_tokens": 4096,
    # JSON mode: the reply must be a JSON object. (Prompts must mention JSON for this mode.)
    "response_format": {"type": "json_object"},
}

# Retry policy
MAX_ATTEMPTS = 5                # total requests per call, including the first
MAX_INVALID_OUTPUT_RETRIES = 1  # extra tries when the model's reply isn't usable JSON
BASE_DELAY_SECONDS = 2          # backoff: 2s, 4s, 8s, 16s ... plus up to 1s of jitter
MAX_DELAY_SECONDS = 60          # never wait longer than this between attempts
REQUEST_TIMEOUT_SECONDS = 120

# Pacing: if the last response said fewer tokens than this remain in the current minute,
# wait for the minute window to reset before sending, instead of spending a request on a 429.
MIN_TOKENS_BEFORE_SENDING = 3000

# Groq rate-limit response headers -> readable names. (Groq documents the "requests"
# headers as per-day and the "tokens" headers as per-minute.)
RATE_LIMIT_HEADERS = {
    "x-ratelimit-limit-requests": "requests_per_day_limit",
    "x-ratelimit-remaining-requests": "requests_remaining_today",
    "x-ratelimit-reset-requests": "requests_reset_in",
    "x-ratelimit-limit-tokens": "tokens_per_minute_limit",
    "x-ratelimit-remaining-tokens": "tokens_remaining_this_minute",
    "x-ratelimit-reset-tokens": "tokens_reset_in",
    "retry-after": "retry_after_seconds",
}


class LLMError(Exception):
    """A model call failed for good (non-retryable error, or retries exhausted).

    rate_limited is True when the last refusal was HTTP 429, and retry_after_seconds is how long
    Groq said to wait, so a long-running batch can sleep until its allowance refills.
    """

    def __init__(self, message, rate_limited=False, retry_after_seconds=None):
        super().__init__(message)
        self.rate_limited = rate_limited
        self.retry_after_seconds = retry_after_seconds


class InvalidOutput(Exception):
    """The API answered, but the reply isn't a usable JSON object."""


_client = None
_last_rate_limit = {}       # rate-limit headers from the most recent response
_last_rate_limit_at = 0.0   # time.monotonic() when they were received


def _get_client():
    global _client
    if _client is None:
        load_dotenv(ENV_PATH)  # does not override a GROQ_API_KEY already set in the OS environment
        api_key = os.environ.get("GROQ_API_KEY", "").strip()
        if not api_key:
            raise LLMError(f"GROQ_API_KEY is not set. Paste your Groq key into {ENV_PATH}")
        # max_retries=0 turns off the SDK's hidden retries: every retry happens (and is
        # logged) in call_llm below, so the request count we report is the real one.
        _client = groq.Groq(api_key=api_key, max_retries=0, timeout=REQUEST_TIMEOUT_SECONDS)
    return _client


def call_llm(messages, label):
    """Send one chat request with the shared settings and return the model's JSON reply.

    messages: [{"role": "system" | "user", "content": "..."}, ...]
    label:    short tag stored in the log, e.g. "naive_baseline:CLM-0035"
    Raises LLMError if no usable reply could be obtained.
    """
    client = _get_client()
    usage_total = {"prompt_tokens": 0, "completion_tokens": 0, "reasoning_tokens": 0, "total_tokens": 0}
    invalid_output_retries = 0

    for attempt in range(1, MAX_ATTEMPTS + 1):
        _wait_for_token_budget()
        rate_limited, retry_after = False, None  # set below if the API refuses on a rate limit
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "label": label,
            "attempt": attempt,
            "model": MODEL,
            "settings": GENERATION_SETTINGS,
            "request_messages": messages,
        }
        started = time.monotonic()
        try:
            raw = client.chat.completions.with_raw_response.create(model=MODEL, messages=messages, **GENERATION_SETTINGS)
            rate_limit = _remember_rate_limit(raw.headers)
            completion = raw.parse()
            usage = _usage(completion)
            for key in usage_total:
                usage_total[key] += usage[key]
            log_entry.update(status="ok", usage=usage, rate_limit=rate_limit, raw_response=completion.model_dump())

            data = _parse_json_object(completion)  # raises InvalidOutput
            return {"data": data, "usage": usage_total, "attempts": attempt, "rate_limit": rate_limit, "model": MODEL}

        except InvalidOutput as error:
            log_entry.update(status="invalid_output", error=str(error))
            problem = f"unusable reply: {error}"
            retryable = invalid_output_retries < MAX_INVALID_OUTPUT_RETRIES
            invalid_output_retries += 1
            delay = _backoff(attempt)

        except groq.APIStatusError as error:  # the API answered with an HTTP error
            problem = f"HTTP {error.status_code}: {error}"
            rate_limited = error.status_code == 429
            retry_after = _retry_after_seconds(error.response.headers)
            retryable, delay = _classify_status_error(error, attempt)
            if _error_code(error) == "json_validate_failed":  # model produced invalid JSON
                retryable = invalid_output_retries < MAX_INVALID_OUTPUT_RETRIES
                invalid_output_retries += 1
            log_entry.update(status="http_error", http_status=error.status_code, error=str(error),
                             retryable=retryable, rate_limit=_remember_rate_limit(error.response.headers))

        except groq.APIConnectionError as error:  # network problem or timeout, no answer at all
            problem = f"{error.__class__.__name__}: {error}"
            retryable, delay = True, _backoff(attempt)
            log_entry.update(status="connection_error", error=problem, retryable=True)

        finally:
            log_entry["duration_ms"] = round((time.monotonic() - started) * 1000)
            _write_log(log_entry)

        if not retryable or attempt == MAX_ATTEMPTS:
            raise LLMError(f"{label}: gave up after {attempt} attempt(s). Last problem: {problem}",
                           rate_limited=rate_limited, retry_after_seconds=retry_after)
        time.sleep(delay)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _wait_for_token_budget():
    """Sleep until the per-minute token window resets if the last response said it's nearly spent."""
    try:
        remaining = int(_last_rate_limit.get("tokens_remaining_this_minute"))
    except (TypeError, ValueError):
        return
    reset_in = _duration_seconds(_last_rate_limit.get("tokens_reset_in"))
    if remaining >= MIN_TOKENS_BEFORE_SENDING or reset_in is None:
        return
    wait = reset_in - (time.monotonic() - _last_rate_limit_at) + 0.5
    if wait > 0:
        time.sleep(min(wait, MAX_DELAY_SECONDS))


def _remember_rate_limit(headers):
    global _last_rate_limit, _last_rate_limit_at
    rate_limit = {name: headers.get(header) for header, name in RATE_LIMIT_HEADERS.items() if headers.get(header) is not None}
    if rate_limit:
        _last_rate_limit, _last_rate_limit_at = rate_limit, time.monotonic()
    return rate_limit


def _duration_seconds(text):
    """Parse Groq reset times like "13.605s", "1m26.4s" or "250ms" into seconds."""
    if not text:
        return None
    units = {"h": 3600, "m": 60, "s": 1, "ms": 0.001}
    parts = re.findall(r"([\d.]+)(ms|h|m|s)", str(text))
    return sum(float(amount) * units[unit] for amount, unit in parts) if parts else None


def _classify_status_error(error, attempt):
    """Return (retryable, seconds_to_wait) for an HTTP error response."""
    status = error.status_code
    if status == 429 or status == 408 or status == 498 or status >= 500:
        retry_after = _retry_after_seconds(error.response.headers)
        if retry_after is not None and retry_after > MAX_DELAY_SECONDS:
            # A long wait usually means the DAILY quota is used up - retrying now just fails.
            return False, 0
        return True, retry_after if retry_after is not None else _backoff(attempt)
    return False, 0  # 400 bad request, 401 bad key, 404 unknown model, 413 too large, ...


def _backoff(attempt):
    return min(BASE_DELAY_SECONDS * 2 ** (attempt - 1), MAX_DELAY_SECONDS) + random.uniform(0, 1)


def _retry_after_seconds(headers):
    try:
        return float(headers.get("retry-after"))
    except (TypeError, ValueError):
        return None


def _error_code(error):
    body = error.body if isinstance(error.body, dict) else {}
    details = body.get("error", body)
    return details.get("code") if isinstance(details, dict) else None


def _usage(completion):
    usage = completion.usage
    details = getattr(usage, "completion_tokens_details", None)
    return {
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "reasoning_tokens": (getattr(details, "reasoning_tokens", None) or 0) if details else 0,
        "total_tokens": usage.total_tokens,
    }


def _parse_json_object(completion):
    choice = completion.choices[0]
    if choice.finish_reason == "length":
        raise InvalidOutput("reply was cut off by max_completion_tokens")
    try:
        data = json.loads(choice.message.content or "")
    except json.JSONDecodeError as error:
        raise InvalidOutput(f"reply is not valid JSON ({error})") from error
    if not isinstance(data, dict):
        raise InvalidOutput("reply is JSON but not an object")
    return data


def _write_log(entry):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"{datetime.now(timezone.utc):%Y-%m-%d}.jsonl"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, default=str) + "\n")
