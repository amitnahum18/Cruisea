"""Adversarial/property-based tests for CruiseSearchParams and search_cruises.

Invariant every test here enforces: constructing CruiseSearchParams, or
calling search_cruises, may only ever raise pydantic.ValidationError or an
ApifyError subclass. Any other exception type is a real bug in src/cruises.py
that must be fixed before shipping.
"""
from unittest.mock import patch

from hypothesis import given, strategies as st
from pydantic import ValidationError

import cruises
from errors import ApifyError
from cruises import CruiseSearchParams, search_cruises

VALID = {"start_date": "2026-06-01", "end_date": "2026-06-30"}


def _construct(**kwargs):
    try:
        CruiseSearchParams(**kwargs)
    except ValidationError:
        pass


@given(st.text())
def test_start_date_never_crashes(value):
    _construct(**{**VALID, "start_date": value})


@given(st.text())
def test_end_date_never_crashes(value):
    _construct(**{**VALID, "end_date": value})


@given(
    st.integers(min_value=1, max_value=13),
    st.integers(min_value=1, max_value=32),
    st.integers(min_value=1, max_value=9999),
)
def test_malformed_calendar_dates_never_crash(month, day, year):
    value = f"{year:04d}-{month:02d}-{day:02d}"
    _construct(**{**VALID, "start_date": value})


@given(st.text())
def test_cruise_length_never_crashes(value):
    _construct(**{**VALID, "cruise_length": value})


@given(st.text())
def test_destination_never_crashes(value):
    _construct(**{**VALID, "destination": value})


@given(st.text())
def test_ship_type_never_crashes(value):
    _construct(**{**VALID, "ship_type": value})


@given(st.text())
def test_ship_name_never_crashes(value):
    _construct(**{**VALID, "ship_name": value})


@given(st.text())
def test_cruise_line_never_crashes(value):
    _construct(**{**VALID, "cruise_line": value})


@given(st.text())
def test_departure_port_never_crashes(value):
    _construct(**{**VALID, "departure_port": value})


@given(st.text())
def test_port_of_call_never_crashes(value):
    _construct(**{**VALID, "port_of_call": value})


@given(st.integers())
def test_max_number_of_pages_never_crashes(value):
    _construct(**{**VALID, "max_number_of_pages": value})


@given(
    st.one_of(
        st.none(),
        st.booleans(),
        st.integers(),
        st.floats(allow_nan=False),
        st.text(),
        st.lists(st.text(), max_size=5),
        st.dictionaries(st.text(max_size=5), st.text(max_size=5), max_size=3),
    )
)
def test_search_cruises_never_crashes_on_weird_stop_text(value):
    fake_items = [{"id": "x", "cruise_title": "t", "stop_1_text": value}]
    with patch.object(cruises, "run_actor_sync", lambda actor_id, data: fake_items):
        try:
            search_cruises(VALID)
        except ApifyError:
            pass


@given(
    st.lists(
        st.one_of(
            st.fixed_dictionaries({"id": st.text(max_size=10)}),
            st.text(),
            st.integers(),
            st.none(),
            st.booleans(),
        ),
        max_size=5,
    )
)
def test_search_cruises_never_crashes_on_non_dict_items(items):
    with patch.object(cruises, "run_actor_sync", lambda actor_id, data: items):
        try:
            search_cruises(VALID)
        except ApifyError:
            pass


def test_valid_params_round_trip_through_model_dump():
    params = CruiseSearchParams(**VALID)
    reloaded = CruiseSearchParams(**params.model_dump(exclude_none=True))
    assert reloaded == params
