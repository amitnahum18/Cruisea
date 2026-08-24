from unittest.mock import patch

import pytest
import requests

import apify_client
from errors import (
    ApifyAuthError,
    ApifyConfigError,
    ApifyError,
    ApifyRateLimitError,
    ApifyResponseError,
    ApifyRunFailedError,
    ApifyTimeoutError,
)


class FakeResponse:
    def __init__(self, status_code, json_data=None, text="", headers=None):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text
        self.headers = headers or {}
        self.ok = 200 <= status_code < 300

    def json(self):
        if self._json_data is None:
            raise ValueError("no json body")
        return self._json_data


def test_missing_token_raises_config_error(monkeypatch):
    monkeypatch.delenv("APIFY_API_TOKEN", raising=False)
    with pytest.raises(ApifyConfigError):
        apify_client.run_actor_sync("someone~actor", {})


def test_success_returns_dataset_items():
    with patch("apify_client.requests.post", return_value=FakeResponse(200, json_data=[{"a": 1}])):
        result = apify_client.run_actor_sync("someone~actor", {}, token="tok")
    assert result == [{"a": 1}]


def test_401_raises_auth_error_without_retry():
    calls = []

    def fake_post(*args, **kwargs):
        calls.append(1)
        return FakeResponse(401, text="unauthorized")

    with patch("apify_client.requests.post", side_effect=fake_post):
        with pytest.raises(ApifyAuthError):
            apify_client.run_actor_sync("someone~actor", {}, token="bad-token")

    assert len(calls) == 1  # auth failures are not retried


def test_400_raises_run_failed_with_actors_own_message():
    body = {"error": {"type": "run-failed", "message": "Actor run did not succeed (FAILED)."}}
    with patch("apify_client.requests.post", return_value=FakeResponse(400, json_data=body)):
        with pytest.raises(ApifyRunFailedError, match="did not succeed"):
            apify_client.run_actor_sync("someone~actor", {}, token="tok")


def test_429_retries_then_raises_rate_limit(monkeypatch):
    monkeypatch.setattr(apify_client.time, "sleep", lambda _: None)
    responses = [FakeResponse(429, headers={"Retry-After": "1"}) for _ in range(3)]

    with patch("apify_client.requests.post", side_effect=responses):
        with pytest.raises(ApifyRateLimitError):
            apify_client.run_actor_sync("someone~actor", {}, token="tok", max_retries=3)


def test_5xx_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr(apify_client.time, "sleep", lambda _: None)
    responses = [FakeResponse(503, text="down"), FakeResponse(200, json_data=[{"ok": True}])]

    with patch("apify_client.requests.post", side_effect=responses):
        result = apify_client.run_actor_sync("someone~actor", {}, token="tok", max_retries=3)

    assert result == [{"ok": True}]


def test_5xx_exhausts_retries_and_raises(monkeypatch):
    monkeypatch.setattr(apify_client.time, "sleep", lambda _: None)
    responses = [FakeResponse(500, text="down") for _ in range(3)]

    with patch("apify_client.requests.post", side_effect=responses):
        with pytest.raises(ApifyError):
            apify_client.run_actor_sync("someone~actor", {}, token="tok", max_retries=3)


def test_timeout_retries_then_raises_timeout_error(monkeypatch):
    monkeypatch.setattr(apify_client.time, "sleep", lambda _: None)

    with patch("apify_client.requests.post", side_effect=requests.exceptions.Timeout("slow")):
        with pytest.raises(ApifyTimeoutError):
            apify_client.run_actor_sync("someone~actor", {}, token="tok", max_retries=2, timeout=5)


def test_connection_error_retries_then_raises(monkeypatch):
    monkeypatch.setattr(apify_client.time, "sleep", lambda _: None)

    with patch(
        "apify_client.requests.post",
        side_effect=requests.exceptions.ConnectionError("dns failure"),
    ):
        with pytest.raises(ApifyError):
            apify_client.run_actor_sync("someone~actor", {}, token="tok", max_retries=2)


def test_non_list_json_raises_response_error():
    with patch("apify_client.requests.post", return_value=FakeResponse(200, json_data={"not": "a list"})):
        with pytest.raises(ApifyResponseError):
            apify_client.run_actor_sync("someone~actor", {}, token="tok")


def test_non_json_body_raises_response_error():
    with patch("apify_client.requests.post", return_value=FakeResponse(200, json_data=None, text="not json")):
        with pytest.raises(ApifyResponseError):
            apify_client.run_actor_sync("someone~actor", {}, token="tok")
