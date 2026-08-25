"""Adversarial/property-based tests for run_actor_sync.

Invariant: whatever the HTTP layer returns, run_actor_sync may only ever
raise an ApifyError subclass (never a raw exception type). This drives
arbitrary status codes, response bodies, and header values through the
retry/error-classification state machine in src/apify_client.py.
"""
from unittest.mock import patch

from hypothesis import given, settings, strategies as st

import apify_client
from errors import ApifyError


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


@given(
    status_code=st.integers(min_value=100, max_value=599),
    body=st.one_of(
        st.none(),
        st.text(),
        st.integers(),
        st.floats(allow_nan=False),
        st.booleans(),
        st.lists(
            st.one_of(st.text(), st.integers(), st.dictionaries(st.text(max_size=10), st.text(max_size=10))),
            max_size=5,
        ),
        st.dictionaries(st.text(max_size=10), st.text(max_size=10), max_size=5),
    ),
)
@settings(max_examples=150)
def test_run_actor_sync_only_raises_apify_error(status_code, body):
    with patch.object(apify_client.time, "sleep", lambda *_: None):
        with patch.object(
            apify_client.requests, "post", return_value=FakeResponse(status_code, json_data=body)
        ):
            try:
                apify_client.run_actor_sync("someone~actor", {}, token="tok", max_retries=1)
            except ApifyError:
                pass


@given(retry_after=st.text())
@settings(max_examples=50)
def test_run_actor_sync_handles_malformed_retry_after_header(retry_after):
    with patch.object(apify_client.time, "sleep", lambda *_: None):
        with patch.object(
            apify_client.requests,
            "post",
            return_value=FakeResponse(429, headers={"Retry-After": retry_after}),
        ):
            try:
                apify_client.run_actor_sync("someone~actor", {}, token="tok", max_retries=2)
            except ApifyError:
                pass


@given(
    error_body=st.one_of(
        st.none(),
        st.text(),
        st.integers(),
        st.lists(st.text(), max_size=5),
        st.dictionaries(st.text(max_size=10), st.text(max_size=10), max_size=5),
    )
)
def test_run_failed_error_body_shape_never_crashes(error_body):
    with patch.object(
        apify_client.requests, "post", return_value=FakeResponse(400, json_data={"error": error_body})
    ):
        try:
            apify_client.run_actor_sync("someone~actor", {}, token="tok")
        except ApifyError:
            pass
