import pytest
from pydantic import ValidationError

import cruises
from cruises import CruiseResult, CruiseSearchParams, search_cruises
from errors import ApifyRunFailedError

VALID = {"start_date": "2026-06-01", "end_date": "2026-06-30"}


def test_requires_start_and_end_date():
    with pytest.raises(ValidationError):
        CruiseSearchParams()


def test_wrong_date_format_from_actors_own_docs_is_rejected():
    # The actor's schema says DD-MMM-YYYY; its real code needs YYYY-MM-DD.
    # We must reject the documented-but-wrong format with a clear message.
    with pytest.raises(ValidationError, match="YYYY-MM-DD"):
        CruiseSearchParams(start_date="01-Jun-2026", end_date="30-Jun-2026")


def test_end_before_start_rejected():
    with pytest.raises(ValidationError, match="before start_date"):
        CruiseSearchParams(start_date="2026-06-30", end_date="2026-06-01")


def test_defaults():
    params = CruiseSearchParams(**VALID)
    assert (params.cruise_length, params.destination, params.ship_type, params.max_number_of_pages) == (
        "0", "0", "0", -1,
    )


@pytest.mark.parametrize("field,value", [
    ("cruise_length", "9"),
    ("destination", "99"),
    ("ship_type", "5"),
])
def test_invalid_enum_codes_rejected(field, value):
    with pytest.raises(ValidationError):
        CruiseSearchParams(**VALID, **{field: value})


@pytest.mark.parametrize("field", ["ship_name", "cruise_line", "departure_port", "port_of_call"])
def test_blank_free_text_rejected(field):
    with pytest.raises(ValidationError, match="not be blank"):
        CruiseSearchParams(**VALID, **{field: "   "})


def test_free_text_accepts_any_non_blank_value():
    # Deliberately not validated against Apify's picklist — see module docstring.
    params = CruiseSearchParams(**VALID, ship_name="Some Future Ship Not Yet In The List")
    assert params.ship_name == "Some Future Ship Not Yet In The List"


def test_max_number_of_pages_zero_rejected():
    with pytest.raises(ValidationError, match="not 0"):
        CruiseSearchParams(**VALID, max_number_of_pages=0)


def test_max_number_of_pages_allows_all_pages_sentinel():
    params = CruiseSearchParams(**VALID, max_number_of_pages=-1)
    assert params.max_number_of_pages == -1


def test_max_number_of_pages_upper_bound_enforced():
    with pytest.raises(ValidationError):
        CruiseSearchParams(**VALID, max_number_of_pages=51)


def test_search_cruises_builds_itinerary_from_stop_fields(monkeypatch):
    fake_items = [
        {
            "id": "abc123",
            "cruise_title": "8 Night Chesapeake Bay Cruise",
            "cruise_line": "American Cruise Lines",
            "ship_name": "ACL American Legend",
            "cruise_date": "2026 Jun 01",
            "cruise_price": "$6995",
            "stop_1_text": "Baltimore, Maryland",
            "stop_2_text": "",
            "stop_3_text": "Annapolis MD, Maryland",
        }
    ]
    monkeypatch.setattr(cruises, "run_actor_sync", lambda actor_id, data: fake_items)

    results = search_cruises(VALID)

    assert len(results) == 1
    assert isinstance(results[0], CruiseResult)
    assert results[0].itinerary == "Baltimore, Maryland -> Annapolis MD, Maryland"


def test_search_cruises_propagates_apify_errors(monkeypatch):
    def boom(actor_id, data):
        raise ApifyRunFailedError("upstream site blocked the request")

    monkeypatch.setattr(cruises, "run_actor_sync", boom)

    with pytest.raises(ApifyRunFailedError):
        search_cruises(VALID)


def test_no_cruises_returns_empty_list(monkeypatch):
    monkeypatch.setattr(cruises, "run_actor_sync", lambda actor_id, data: [])
    assert search_cruises(VALID) == []
