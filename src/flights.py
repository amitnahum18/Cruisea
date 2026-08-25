"""Production-ready wrapper around johnvc/Google-Flights-Data-Scraper.

Validation is deliberately stricter than the actor's own JSON Schema (which
declares nothing as `required` — the "required" language only lives in each
field's prose description). departure_id / arrival_id / outbound_date are
enforced here unless multi_city_json is supplied instead.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from apify_client import run_actor_sync

ACTOR_ID = "johnvc~Google-Flights-Data-Scraper-Flight-and-Price-Search"

_AIRPORT_CODES_RE = re.compile(r"^[A-Z]{3}(,[A-Z]{3})*$")

# From the actor's input schema enums — stable, small pick-lists worth enforcing.
_LANGUAGE_CODES = {
    "en", "es", "fr", "de", "it", "pt", "ru", "ja", "ko", "zh", "ar", "hi", "tr", "pl",
    "nl", "sv", "da", "no", "fi", "cs", "hu", "ro", "el", "th", "vi", "id", "ms", "he", "uk",
}
_COUNTRY_CODES = {
    "us", "uk", "ca", "au", "de", "fr", "es", "it", "nl", "pl", "br", "ru", "jp", "kr",
    "cn", "tw", "in", "sa", "tr", "se", "dk", "no", "fi", "cz", "hu", "ro", "mx", "ar",
    "ch", "at", "be", "ie", "nz", "sg", "my", "th", "ph", "id", "vn",
}


def _parse_date(value: str, field_name: str) -> str:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"{field_name} must be YYYY-MM-DD, got {value!r}") from exc
    return value


class FlightSearchParams(BaseModel):
    model_config = {"str_strip_whitespace": True}

    departure_id: Optional[str] = None
    arrival_id: Optional[str] = None
    outbound_date: Optional[str] = None
    return_date: Optional[str] = None
    multi_city_json: Optional[str] = None

    adults: int = Field(default=1, ge=1, le=9)
    children: int = Field(default=0, ge=0, le=8)
    infants: int = Field(default=0, ge=0, le=8)

    currency: str = "USD"
    hl: str = "en"
    gl: str = "us"

    max_price: Optional[int] = Field(default=None, gt=0)
    max_stops: Optional[int] = Field(default=None, ge=0, le=3)
    airlines: Optional[str] = None
    exclude_basic: bool = False
    fetch_booking_options: bool = False
    # 0 = "no limit" per the actor's own docs — deliberately allowed, but it can
    # make the run slow/expensive; capped here so a stray value can't run away.
    max_pages: int = Field(default=1, ge=0, le=10)

    @field_validator("departure_id", "arrival_id")
    @classmethod
    def _validate_airport_codes(cls, v: Optional[str], info) -> Optional[str]:
        if v is None:
            return v
        v = v.upper().replace(" ", "")
        if not _AIRPORT_CODES_RE.match(v):
            raise ValueError(
                f"{info.field_name} must be comma-separated 3-letter airport codes (e.g. 'LAX' or 'CDG,ORY'), got {v!r}"
            )
        return v

    @field_validator("outbound_date")
    @classmethod
    def _validate_outbound_date(cls, v: Optional[str]) -> Optional[str]:
        return _parse_date(v, "outbound_date") if v else v

    @field_validator("return_date")
    @classmethod
    def _validate_return_date(cls, v: Optional[str]) -> Optional[str]:
        return _parse_date(v, "return_date") if v else v

    @field_validator("currency")
    @classmethod
    def _validate_currency(cls, v: str) -> str:
        v = v.upper()
        if not re.match(r"^[A-Z]{3}$", v):
            raise ValueError(f"currency must be a 3-letter code (e.g. 'USD'), got {v!r}")
        return v

    @field_validator("hl")
    @classmethod
    def _validate_hl(cls, v: str) -> str:
        v = v.lower()
        if v not in _LANGUAGE_CODES:
            raise ValueError(f"hl must be one of {sorted(_LANGUAGE_CODES)}, got {v!r}")
        return v

    @field_validator("gl")
    @classmethod
    def _validate_gl(cls, v: str) -> str:
        v = v.lower()
        if v not in _COUNTRY_CODES:
            raise ValueError(f"gl must be one of {sorted(_COUNTRY_CODES)}, got {v!r}")
        return v

    @field_validator("multi_city_json")
    @classmethod
    def _validate_multi_city_json(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        try:
            legs = json.loads(v)
        except json.JSONDecodeError as exc:
            raise ValueError(f"multi_city_json is not valid JSON: {exc}") from exc
        if not isinstance(legs, list) or not legs:
            raise ValueError("multi_city_json must be a non-empty JSON array of legs")
        for i, leg in enumerate(legs):
            if not isinstance(leg, dict):
                raise ValueError(f"multi_city_json[{i}] must be an object")
            missing = {"departure_id", "arrival_id", "date"} - leg.keys()
            if missing:
                raise ValueError(f"multi_city_json[{i}] is missing {sorted(missing)}")
        return v

    @model_validator(mode="after")
    def _require_route_or_multi_city(self) -> "FlightSearchParams":
        if self.multi_city_json:
            return self
        missing = [f for f in ("departure_id", "arrival_id", "outbound_date") if getattr(self, f) is None]
        if missing:
            raise ValueError(
                f"Missing required field(s) for a one-way/round-trip search: {missing}. "
                "Provide these, or use multi_city_json for a multi-city trip."
            )
        return self

    @model_validator(mode="after")
    def _return_after_outbound(self) -> "FlightSearchParams":
        if self.return_date and self.outbound_date and self.return_date < self.outbound_date:
            raise ValueError(f"return_date ({self.return_date}) is before outbound_date ({self.outbound_date})")
        return self


class FlightResult(BaseModel):
    model_config = {"extra": "ignore"}

    airlines: Optional[str] = None
    route: Optional[str] = None
    departure_airport: Optional[str] = None
    departure_time: Optional[str] = None
    arrival_airport: Optional[str] = None
    arrival_time: Optional[str] = None
    stops: Optional[int] = None
    stops_label: Optional[str] = None
    duration: Optional[str] = None
    duration_minutes: Optional[int] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    travel_class: Optional[str] = None
    flight_numbers: Optional[str] = None
    category: Optional[str] = None


FLIGHT_TABLE_COLUMNS = [
    ("airline", "airlines"),
    ("route", "route"),
    ("departure", "departure_time"),
    ("arrival", "arrival_time"),
    ("stops", "stops_label"),
    ("duration", "duration"),
    ("price", "price"),
    ("currency", "currency"),
]


def search_flights(params: FlightSearchParams | dict) -> list[FlightResult]:
    """Validate params, run the actor, and return typed flight rows.

    Raises pydantic.ValidationError for bad input (no network call is made),
    and the ApifyError subclasses from errors.py for anything that fails on
    Apify's side.
    """
    if isinstance(params, dict):
        params = FlightSearchParams(**params)

    items = run_actor_sync(ACTOR_ID, params.model_dump(exclude_none=True))
    flights = [
        f
        for item in items
        if isinstance(item, dict) and isinstance(item.get("all_flights"), list)
        for f in item["all_flights"]
        if isinstance(f, dict)
    ]
    return [FlightResult.model_validate(f) for f in flights]
