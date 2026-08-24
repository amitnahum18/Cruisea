# Cruisea

Typed, validated Python wrappers around two Apify actors:

- **Flights** — `johnvc/Google-Flights-Data-Scraper-Flight-and-Price-Search`
- **Cruises** — `vulnv/cruisemapper-cruises-scraper`

Each is a plain function (`search_flights`, `search_cruises`) backed by a Pydantic
model that enforces required fields, types, and value ranges *before* any network
call is made — see `src/flights.py` and `src/cruises.py` for the exact rules.

## Setup

```bash
pip install -r requirements-dev.txt
export APIFY_API_TOKEN=apify_api_...
```

## Usage

```bash
python src/main.py flights search.example.json
python src/main.py cruises search_cruises.example.json
```

```python
from flights import search_flights
from cruises import search_cruises

flights = search_flights({"departure_id": "TLV", "arrival_id": "JFK", "outbound_date": "2026-09-18"})
cruises = search_cruises({"start_date": "2026-06-01", "end_date": "2026-06-30"})
```

## Development

```bash
pytest -v
ruff check src tests
```

CI runs both on every push and pull request against `main` (see `.github/workflows/ci.yml`).
