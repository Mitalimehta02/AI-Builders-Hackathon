"""
Offline tests for the shared Groq client: retries, give-up rules, pacing and logging.
A fake client stands in for Groq, so these tests never use the network or any quota.

Run from the backend/ folder:
    .\\.venv\\Scripts\\python.exe -m pytest tests -v
"""

import json
from types import SimpleNamespace

import groq
import httpx
import pytest

from app.agents import llm_client


def http_error(error_class, status, headers=None):
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(status, headers=headers or {}, request=request)
    return error_class(f"simulated {status}", response=response, body=None)


def ok_reply(content='{"decision": "APPROVE", "confidence": 80, "reasoning": "fine"}', finish_reason="stop"):
    completion = SimpleNamespace(
        choices=[SimpleNamespace(finish_reason=finish_reason, message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=100, completion_tokens=50, total_tokens=150,
                              completion_tokens_details=SimpleNamespace(reasoning_tokens=30)),
    )
    completion.model_dump = lambda: {"simulated": True, "content": content}
    return SimpleNamespace(parse=lambda: completion, headers={"x-ratelimit-remaining-requests": "999"})


class FakeGroq:
    """Plays back a scripted list of outcomes: an exception to raise, or a reply to return."""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(with_raw_response=SimpleNamespace(create=self._create)))

    def _create(self, **kwargs):
        self.calls += 1
        assert kwargs["model"] == llm_client.MODEL
        for name, value in llm_client.GENERATION_SETTINGS.items():
            assert kwargs[name] == value, f"call used a different {name}"
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture
def fake(monkeypatch, tmp_path):
    """Install a fake client, log to a temp folder, forget past rate limits, skip real sleeping."""
    def install(outcomes):
        client = FakeGroq(outcomes)
        monkeypatch.setattr(llm_client, "_get_client", lambda: client)
        return client

    monkeypatch.setattr(llm_client, "LOG_DIR", tmp_path)
    monkeypatch.setattr(llm_client, "_last_rate_limit", {})
    monkeypatch.setattr(llm_client.time, "sleep", lambda seconds: None)
    install.log_lines = lambda: [json.loads(line) for f in tmp_path.glob("*.jsonl") for line in f.read_text().splitlines()]
    return install


MESSAGES = [{"role": "user", "content": "Reply in JSON."}]


def test_success_returns_parsed_json_usage_and_logs(fake):
    client = fake([ok_reply()])
    result = llm_client.call_llm(MESSAGES, label="test")
    assert result["data"]["decision"] == "APPROVE"
    assert result["attempts"] == 1 and client.calls == 1
    assert result["usage"] == {"prompt_tokens": 100, "completion_tokens": 50, "reasoning_tokens": 30, "total_tokens": 150}
    (entry,) = fake.log_lines()
    assert entry["status"] == "ok" and entry["request_messages"] == MESSAGES
    assert entry["usage"]["total_tokens"] == 150 and entry["raw_response"]["simulated"] is True
    assert entry["settings"] == json.loads(json.dumps(llm_client.GENERATION_SETTINGS)) and "timestamp" in entry


def test_retries_rate_limit_and_connection_errors_then_succeeds(fake):
    request = httpx.Request("POST", "https://api.groq.com")
    client = fake([
        http_error(groq.RateLimitError, 429, {"retry-after": "3"}),
        groq.APIConnectionError(request=request),
        ok_reply(),
    ])
    result = llm_client.call_llm(MESSAGES, label="test")
    assert result["attempts"] == 3 and client.calls == 3
    assert [e["status"] for e in fake.log_lines()] == ["http_error", "connection_error", "ok"]


def test_gives_up_after_max_attempts(fake):
    client = fake([http_error(groq.InternalServerError, 503)] * llm_client.MAX_ATTEMPTS)
    with pytest.raises(llm_client.LLMError):
        llm_client.call_llm(MESSAGES, label="test")
    assert client.calls == llm_client.MAX_ATTEMPTS
    assert len(fake.log_lines()) == llm_client.MAX_ATTEMPTS


def test_does_not_retry_bad_key(fake):
    client = fake([http_error(groq.AuthenticationError, 401)])
    with pytest.raises(llm_client.LLMError) as caught:
        llm_client.call_llm(MESSAGES, label="test")
    assert client.calls == 1
    assert caught.value.rate_limited is False


def test_stops_immediately_when_quota_reset_is_far_away(fake):
    # A retry-after longer than MAX_DELAY_SECONDS usually means the daily quota is used up.
    client = fake([http_error(groq.RateLimitError, 429, {"retry-after": "3600"})])
    with pytest.raises(llm_client.LLMError) as caught:
        llm_client.call_llm(MESSAGES, label="test")
    assert client.calls == 1
    # The Stage 11 batch uses these to sleep until the daily allowance refills.
    assert caught.value.rate_limited is True and caught.value.retry_after_seconds == 3600


def test_invalid_output_is_retried_only_once(fake):
    client = fake([ok_reply(content="not json"), ok_reply(content="", finish_reason="length")])
    with pytest.raises(llm_client.LLMError):
        llm_client.call_llm(MESSAGES, label="test")
    assert client.calls == 2
    assert [e["status"] for e in fake.log_lines()] == ["invalid_output", "invalid_output"]


def test_waits_for_token_window_when_nearly_out_of_tokens(fake, monkeypatch):
    slept = []
    monkeypatch.setattr(llm_client.time, "sleep", lambda seconds: slept.append(seconds))
    monkeypatch.setattr(llm_client, "_last_rate_limit", {"tokens_remaining_this_minute": "500", "tokens_reset_in": "12.5s"})
    monkeypatch.setattr(llm_client, "_last_rate_limit_at", llm_client.time.monotonic())
    fake([ok_reply()])
    llm_client.call_llm(MESSAGES, label="test")
    assert len(slept) == 1 and 11 <= slept[0] <= 13.5


def test_does_not_wait_when_token_budget_is_fine(fake, monkeypatch):
    slept = []
    monkeypatch.setattr(llm_client.time, "sleep", lambda seconds: slept.append(seconds))
    monkeypatch.setattr(llm_client, "_last_rate_limit", {"tokens_remaining_this_minute": "7000", "tokens_reset_in": "12.5s"})
    fake([ok_reply()])
    llm_client.call_llm(MESSAGES, label="test")
    assert slept == []


def test_groq_reset_durations_are_parsed():
    assert llm_client._duration_seconds("1m26.4s") == pytest.approx(86.4)
    assert llm_client._duration_seconds("13.605s") == pytest.approx(13.605)
    assert llm_client._duration_seconds("250ms") == pytest.approx(0.25)
    assert llm_client._duration_seconds(None) is None
