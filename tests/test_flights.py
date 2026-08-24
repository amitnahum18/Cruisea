import pytest
from pydantic import ValidationError

import flights
from flights import FlightResult, FlightSearchParams, search_flights
from errors import ApifyRunFailedError

VALID = {
    "departure_id": "TLV",
    "arrival_id": "JFK",
    "outbound_date": "2026-09-18",
}


def test_missing_required_fields_rejected():
    with pytest.raises(ValidationError, match="Missing required field"):
        FlightSearchParams()


def test_multi_city_bypasses_single_leg_requirement():
    legs = '[{"departure_id":"TLV","arrival_id":"JFK","date":"2026-09-18"}]'
    params = FlightSearchParams(multi_city_json=legs)
    assert params.departure_id is None


def test_multi_city_json_must_be_valid_json():
    with pytest.raises(ValidationError, match="not valid JSON"):
        FlightSearchParams(multi_city_json="not json")


def test_multi_city_leg_missing_keys_rejected():
    with pytest.raises(ValidationError, match="missing"):
        FlightSearchParams(multi_city_json='[{"departure_id":"TLV"}]')


@pytest.mark.parametrize("field,value", [("departure_id", "TelAviv"), ("arrival_id", "123")])
def test_invalid_airport_code_rejected(field, value):
    with pytest.raises(ValidationError, match="airport codes"):
        FlightSearchParams(**{**VALID, field: value})


def test_airport_codes_normalized_uppercase():
    params = FlightSearchParams(**{**VALID, "departure_id": "tlv"})
    assert params.departure_id == "TLV"


def test_multi_airport_codes_accepted():
    params = FlightSearchParams(**{**VALID, "departure_id": "CDG,ORY"})
    assert params.departure_id == "CDG,ORY"


def test_invalid_date_format_rejected():
    with pytest.raises(ValidationError, match="YYYY-MM-DD"):
        FlightSearchParams(**{**VALID, "outbound_date": "18-09-2026"})


def test_return_before_outbound_rejected():
    with pytest.raises(ValidationError, match="before outbound_date"):
        FlightSearchParams(**VALID, return_date="2026-09-01")


def test_defaults():
    params = FlightSearchParams(**VALID)
    assert (params.adults, params.currency, params.hl, params.gl) == (1, "USD", "en", "us")


def test_invalid_hl_rejected():
    with pytest.raises(ValidationError, match="hl must be one of"):
        FlightSearchParams(**VALID, hl="xx")


def test_invalid_gl_rejected():
    with pytest.raises(ValidationError, match="gl must be one of"):
        FlightSearchParams(**VALID, gl="xx")


def test_invalid_currency_rejected():
    with pytest.raises(ValidationError, match="currency must be a 3-letter code"):
        FlightSearchParams(**VALID, currency="US")


def test_adults_must_be_at_least_one():
    with pytest.raises(ValidationError):
        FlightSearchParams(**VALID, adults=0)


def test_search_flights_happy_path(monkeypatch):
    fake_items = [
        {
            "all_flights": [
                {
                    "airlines": "Air France",
                    "route": "TLV-JFK",
                    "departure_time": "2026-09-18 16:40",
                    "arrival_time": "2026-09-19 10:40",
                    "stops": 1,
                    "stops_label": "1 stop",
                    "duration": "25h",
                    "price": 1572,
                    "currency": "USD",
                }
            ]
        }
    ]
    monkeypatch.setattr(flights, "run_actor_sync", lambda actor_id, data: fake_items)

    results = search_flights(VALID)

    assert len(results) == 1
    assert isinstance(results[0], FlightResult)
    assert results[0].airlines == "Air France"
    assert results[0].price == 1572


def test_search_flights_accepts_plain_dict_and_validates_first(monkeypatch):
    monkeypatch.setattr(flights, "run_actor_sync", lambda actor_id, data: (_ for _ in ()).throw(
        AssertionError("network should not be called for invalid input")
    ))
    with pytest.raises(ValidationError):
        search_flights({"outbound_date": "2026-09-18"})  # missing departure/arrival


def test_search_flights_propagates_apify_errors(monkeypatch):
    def boom(actor_id, data):
        raise ApifyRunFailedError("target site changed layout")

    monkeypatch.setattr(flights, "run_actor_sync", boom)

    with pytest.raises(ApifyRunFailedError):
        search_flights(VALID)


def test_no_flights_returns_empty_list(monkeypatch):
    monkeypatch.setattr(flights, "run_actor_sync", lambda actor_id, data: [{"all_flights": []}])
    assert search_flights(VALID) == []
