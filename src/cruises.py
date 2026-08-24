"""Production-ready wrapper around vulnv/cruisemapper-cruises-scraper.

The actor's own schema documents start_date/end_date as DD-MMM-YYYY, but its
code actually requires YYYY-MM-DD (confirmed from a failed run's traceback —
see the ValueError message below). Validation here enforces the format that
actually works, not the one the docs claim.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from apify_client import run_actor_sync

ACTOR_ID = "vulnv~cruisemapper-cruises-scraper"

# Small, stable ordinal codes from the actor's schema — safe to hard-enforce.
_CRUISE_LENGTH_CODES = {"0", "1", "2", "3", "4", "5"}
_DESTINATION_CODES = {
    "0", "1", "2", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14",
    "15", "16", "17", "18", "20", "21", "22", "23", "24", "26",
}
_SHIP_TYPE_CODES = {"0", "1", "2"}

_MAX_STOPS_TO_JOIN = 29


def _parse_date(value: str, field_name: str) -> str:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(
            f"{field_name} must be YYYY-MM-DD (the actor's own docs say DD-MMM-YYYY, "
            f"but its code actually requires YYYY-MM-DD), got {value!r}"
        ) from exc
    return value


class CruiseSearchParams(BaseModel):
    model_config = {"str_strip_whitespace": True}

    start_date: str
    end_date: str

    cruise_length: str = "0"
    # ship_name / cruise_line / departure_port / port_of_call are picked from
    # very large, frequently-changing lists (hundreds of ships/ports). We only
    # check they're non-blank — a typo is NOT rejected, it just yields zero
    # results, same as a real query for a ship/port that doesn't sail.
    ship_name: Optional[str] = None
    cruise_line: Optional[str] = None
    departure_port: Optional[str] = None
    destination: str = "0"
    ship_type: str = "0"
    port_of_call: Optional[str] = None
    # -1 = all pages (can be slow/expensive); capped to stop a runaway crawl.
    max_number_of_pages: int = Field(default=-1, ge=-1, le=50)

    @field_validator("start_date", "end_date")
    @classmethod
    def _validate_dates(cls, v: str, info) -> str:
        return _parse_date(v, info.field_name)

    @field_validator("cruise_length")
    @classmethod
    def _validate_cruise_length(cls, v: str) -> str:
        if v not in _CRUISE_LENGTH_CODES:
            raise ValueError(f"cruise_length must be one of {sorted(_CRUISE_LENGTH_CODES)}, got {v!r}")
        return v

    @field_validator("destination")
    @classmethod
    def _validate_destination(cls, v: str) -> str:
        if v not in _DESTINATION_CODES:
            raise ValueError(f"destination must be one of {sorted(_DESTINATION_CODES, key=int)}, got {v!r}")
        return v

    @field_validator("ship_type")
    @classmethod
    def _validate_ship_type(cls, v: str) -> str:
        if v not in _SHIP_TYPE_CODES:
            raise ValueError(f"ship_type must be one of {sorted(_SHIP_TYPE_CODES)}, got {v!r}")
        return v

    @field_validator("ship_name", "cruise_line", "departure_port", "port_of_call")
    @classmethod
    def _validate_free_text(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("must not be blank if provided")
        return v

    @field_validator("max_number_of_pages")
    @classmethod
    def _validate_max_pages(cls, v: int) -> int:
        if v == 0:
            raise ValueError("max_number_of_pages must be -1 (all pages) or a positive integer, not 0")
        return v

    @model_validator(mode="after")
    def _end_after_start(self) -> "CruiseSearchParams":
        if self.end_date < self.start_date:
            raise ValueError(f"end_date ({self.end_date}) is before start_date ({self.start_date})")
        return self


class CruiseResult(BaseModel):
    model_config = {"extra": "ignore"}

    id: Optional[str] = None
    cruise_title: Optional[str] = None
    cruise_line: Optional[str] = None
    ship_name: Optional[str] = None
    cruise_date: Optional[str] = None
    # kept as str: the actor sometimes returns "" when a line doesn't publish price
    cruise_price: Optional[str] = None
    itinerary: str = ""


def _itinerary(item: dict) -> str:
    stops = []
    for i in range(1, _MAX_STOPS_TO_JOIN + 1):
        text = item.get(f"stop_{i}_text")
        if text:
            stops.append(text)
    return " -> ".join(stops)


CRUISE_TABLE_COLUMNS = [
    ("title", "cruise_title"),
    ("line", "cruise_line"),
    ("ship", "ship_name"),
    ("date", "cruise_date"),
    ("price", "cruise_price"),
    ("itinerary", "itinerary"),
]


def search_cruises(params: CruiseSearchParams | dict) -> list[CruiseResult]:
    """Validate params, run the actor, and return typed cruise rows with a
    computed `itinerary` (joined from the actor's stop_1..stop_29 fields).

    Raises pydantic.ValidationError for bad input (no network call is made),
    and the ApifyError subclasses from errors.py for anything that fails on
    Apify's side.
    """
    if isinstance(params, dict):
        params = CruiseSearchParams(**params)

    items = run_actor_sync(ACTOR_ID, params.model_dump(exclude_none=True))
    results = []
    for item in items:
        item["itinerary"] = _itinerary(item)
        results.append(CruiseResult.model_validate(item))
    return results
