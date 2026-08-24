"""Thin, production-hardened wrapper around Apify's synchronous REST endpoint:
retries transient failures, distinguishes error classes, never leaks a raw
requests exception to callers.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

import requests

from errors import (
    ApifyAuthError,
    ApifyConfigError,
    ApifyError,
    ApifyRateLimitError,
    ApifyResponseError,
    ApifyRunFailedError,
    ApifyTimeoutError,
)

logger = logging.getLogger("apify_client")

DEFAULT_TIMEOUT_SECS = 300  # actors can legitimately run for minutes
MAX_RETRIES = 3
BACKOFF_BASE_SECS = 2.0


def run_actor_sync(
    actor_id: str,
    input_data: dict[str, Any],
    token: str | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECS,
    max_retries: int = MAX_RETRIES,
) -> list[dict]:
    """Run an Apify Actor synchronously and return its output dataset items.

    actor_id: "username~actor-name" (tilde, not slash).

    Raises:
        ApifyConfigError    — no token configured.
        ApifyAuthError      — token rejected (401/403); not retried.
        ApifyRateLimitError — 429 after retries exhausted.
        ApifyRunFailedError — the actor ran and failed; not retried (retrying
                               won't fix bad input or a broken target site).
        ApifyTimeoutError   — no response within timeout across all attempts.
        ApifyResponseError  — a 2xx response that wasn't the JSON list we expect.
        ApifyError          — anything else (5xx exhausted, unexpected status).
    """
    token = token or os.environ.get("APIFY_API_TOKEN")
    if not token:
        raise ApifyConfigError("APIFY_API_TOKEN is not set. Export it or pass token= explicitly.")

    url = f"https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items"
    headers = {"Authorization": f"Bearer {token}"}

    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            res = requests.post(url, headers=headers, json=input_data, timeout=timeout)
        except requests.exceptions.Timeout as exc:
            last_error = exc
            logger.warning("Apify request timed out (attempt %d/%d)", attempt, max_retries)
        except requests.exceptions.ConnectionError as exc:
            last_error = exc
            logger.warning("Apify connection error (attempt %d/%d): %s", attempt, max_retries, exc)
        else:
            if res.status_code in (401, 403):
                raise ApifyAuthError(
                    f"Apify rejected the token ({res.status_code}). "
                    "Check APIFY_API_TOKEN and that it has access to this actor."
                )

            if res.status_code == 400:
                _raise_run_failed(res)  # never returns

            if res.status_code == 429:
                if attempt == max_retries:
                    retry_after = _parse_retry_after(res)
                    raise ApifyRateLimitError(
                        "Apify rate-limited this request and retries were exhausted.",
                        retry_after=retry_after,
                    )
                wait = _parse_retry_after(res) or BACKOFF_BASE_SECS * attempt
                logger.warning("Rate limited (attempt %d/%d), retrying in %.1fs", attempt, max_retries, wait)
                time.sleep(wait)
                continue

            if 500 <= res.status_code < 600:
                last_error = ApifyError(f"Apify server error {res.status_code}: {res.text[:500]}")
                logger.warning("Apify 5xx (attempt %d/%d): %s", attempt, max_retries, res.status_code)
            elif not res.ok:
                raise ApifyError(f"Apify API error {res.status_code}: {res.text[:500]}")
            else:
                try:
                    data = res.json()
                except ValueError as exc:
                    raise ApifyResponseError(f"Apify returned non-JSON response: {exc}") from exc
                if not isinstance(data, list):
                    raise ApifyResponseError(f"Expected a list of dataset items, got {type(data).__name__}")
                return data

        if attempt < max_retries:
            time.sleep(BACKOFF_BASE_SECS * attempt)

    if isinstance(last_error, requests.exceptions.Timeout):
        raise ApifyTimeoutError(
            f"Actor did not finish within {timeout}s across {max_retries} attempts."
        ) from last_error
    raise ApifyError(f"Apify request failed after {max_retries} attempts: {last_error}") from last_error


def _parse_retry_after(res: requests.Response) -> float | None:
    value = res.headers.get("Retry-After")
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _raise_run_failed(res: requests.Response) -> None:
    try:
        body = res.json()
        message = body.get("error", {}).get("message", res.text[:500])
    except ValueError:
        message = res.text[:500]
    raise ApifyRunFailedError(message)
