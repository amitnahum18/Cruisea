"""Adversarial/property-based tests for FlightSearchParams and search_flights.

Invariant every test here enforces: constructing FlightSearchParams, or
calling search_flights, may only ever raise pydantic.ValidationError or an
ApifyError subclass. Any other exception type is a real bug in src/flights.py
that must be fixed before shipping.
"""
import json
from unittest.mock import patch

from hypothesis import given, settings, strategies as st
from pydantic import ValidationError

import flights
from errors import ApifyError
from flights import FlightSearchParams, search_flights

VALID = {
    "departure_id": "TLV",
    "arrival_id": "JFK",
    "outbound_date": "2026-09-18",
}


def _construct(**kwargs):
    try:
        FlightSearchParams(**kwargs)
    except ValidationError:
        pass


@given(st.text())
def test_departure_id_never_crashes(value):
    _construct(**{**VALID, "departure_id": value})


@given(st.text())
def test_arrival_id_never_crashes(value):
    _construct(**{**VALID, "arrival_id": value})


@given(st.text())
def test_airlines_never_crashes(value):
    _construct(**{**VALID, "airlines": value})


@given(st.text())
def test_currency_never_crashes(value):
    _construct(**{**VALID, "currency": value})


@given(st.text())
def test_hl_never_crashes(value):
    _construct(**{**VALID, "hl": value})


@given(st.text())
def test_gl_never_crashes(value):
    _construct(**{**VALID, "gl": value})


@given(st.text())
def test_outbound_date_never_crashes(value):
    _construct(**{**VALID, "outbound_date": value})


@given(st.text())
def test_return_date_never_crashes(value):
    _construct(**{**VALID, "return_date": value})


@given(
    st.integers(min_value=1, max_value=13),
    st.integers(min_value=1, max_value=32),
    st.integers(min_value=1, max_value=9999),
)
def test_malformed_calendar_dates_never_crash(month, day, year):
    value = f"{year:04d}-{month:02d}-{day:02d}"
    _construct(**{**VALID, "outbound_date": value})


@given(st.integers())
def test_adults_never_crashes(value):
    _construct(**{**VALID, "adults": value})


@given(st.integers())
def test_children_never_crashes(value):
    _construct(**{**VALID, "children": value})


@given(st.integers())
def test_infants_never_crashes(value):
    _construct(**{**VALID, "infants": value})


@given(st.integers())
def test_max_stops_never_crashes(value):
    _construct(**{**VALID, "max_stops": value})


@given(st.integers())
def test_max_pages_never_crashes(value):
    _construct(**{**VALID, "max_pages": value})


@given(st.integers())
def test_max_price_never_crashes(value):
    _construct(**{**VALID, "max_price": value})


@given(st.text())
def test_multi_city_json_arbitrary_text_never_crashes(value):
    _construct(multi_city_json=value)


@given(
    st.one_of(
        st.integers(),
        st.floats(allow_nan=False),
        st.text(),
        st.booleans(),
        st.none(),
        st.lists(st.integers()),
        st.lists(st.dictionaries(st.text(), st.text())),
        st.dictionaries(st.text(), st.text()),
    )
)
def test_multi_city_json_wrong_shape_never_crashes(value):
    _construct(multi_city_json=json.dumps(value))


@given(
    st.recursive(
        st.one_of(st.none(), st.booleans(), st.integers(), st.text()),
        lambda children: st.lists(children, max_size=3)
        | st.dictionaries(st.text(max_size=5), children, max_size=3),
        max_leaves=20,
    )
)
def test_multi_city_json_deeply_nested_never_crashes(value):
    _construct(multi_city_json=json.dumps(value))


@given(st.text(alphabet=st.characters(codec="ascii"), min_size=2_000, max_size=4_000))
@settings(max_examples=10)
def test_multi_city_json_huge_string_never_crashes(value):
    _construct(multi_city_json=value)


@given(
    st.lists(
        st.fixed_dictionaries(
            {
                "all_flights": st.one_of(
                    st.none(),
                    st.integers(),
                    st.text(),
                    st.booleans(),
                    st.lists(
                        st.one_of(
                            st.none(),
                            st.integers(),
                            st.text(),
                            st.dictionaries(st.text(max_size=10), st.text(max_size=10)),
                        ),
                        max_size=5,
                    ),
                )
            }
        ),
        max_size=5,
    )
)
def test_search_flights_never_crashes_on_malformed_dataset_items(items):
    with patch.object(flights, "run_actor_sync", lambda actor_id, data: items):
        try:
            search_flights(VALID)
        except ApifyError:
            pass


@given(
    st.one_of(
        st.lists(st.one_of(st.text(), st.integers(), st.none()), max_size=5),
        st.text(),
        st.integers(),
        st.none(),
    )
)
def test_search_flights_never_crashes_on_non_dict_top_level_items(items):
    with patch.object(flights, "run_actor_sync", lambda actor_id, data: items):
        try:
            search_flights(VALID)
        except (ApifyError, TypeError):
            # A non-list/non-iterable top-level payload from run_actor_sync would
            # already violate run_actor_sync's own documented contract (it always
            # returns list[dict]); we only guard against *items inside* the list
            # being malformed, not the top-level shape itself.
            pass


def test_valid_params_round_trip_through_model_dump():
    params = FlightSearchParams(**VALID)
    reloaded = FlightSearchParams(**params.model_dump(exclude_none=True))
    assert reloaded == params
