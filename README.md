# Cruisea

Typed, validated Python wrappers around two Apify actors:

- **Flights** — `johnvc/Google-Flights-Data-Scraper-Flight-and-Price-Search`
- **Cruises** — `vulnv/cruisemapper-cruises-scraper`

Each is a plain function (`search_flights`, `search_cruises`) backed by a Pydantic
model that enforces required fields, types, and value ranges *before* any network
call is made — see `src/flights.py` and `src/cruises.py` for the exact rules.

## Setup

```bash
pip install --require-hashes -r requirements-dev.txt
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

### Dependencies

Runtime/dev/security dependencies are declared loosely in `requirements.in` /
`requirements-dev.in` / `requirements-security.in`, then compiled into fully
pinned, hash-locked files with [pip-tools](https://github.com/jazzband/pip-tools):

```bash
pip install pip-tools==7.4.1
pip-compile --generate-hashes --allow-unsafe --no-strip-extras --output-file=requirements.txt requirements.in
pip-compile --generate-hashes --allow-unsafe --no-strip-extras --output-file=requirements-dev.txt requirements-dev.in
pip-compile --generate-hashes --allow-unsafe --no-strip-extras --output-file=requirements-security.txt requirements-security.in
```

CI and local installs use `pip install --require-hashes -r ...`, which refuses
to install anything not pinned by hash — this is what caused the ruff incident
(an unpinned `ruff>=0.5` silently resolved to a newer version in CI with
different default behavior) to become structurally impossible for any
dependency now. To bump a dependency: edit the relevant `.in` file, recompile,
verify locally, and commit the `.in` and `.txt` files together.
