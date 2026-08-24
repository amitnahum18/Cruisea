"""Usage:
    python src/main.py flights search.json
    python src/main.py cruises search_cruises.json
    echo '{...}' | python src/main.py flights
"""
from __future__ import annotations

import json
import sys

from pydantic import ValidationError
from tabulate import tabulate

from cruises import CRUISE_TABLE_COLUMNS, search_cruises
from errors import ApifyError
from flights import FLIGHT_TABLE_COLUMNS, search_flights

SEARCHERS = {
    "flights": (search_flights, FLIGHT_TABLE_COLUMNS),
    "cruises": (search_cruises, CRUISE_TABLE_COLUMNS),
}


def read_search_json() -> dict:
    if len(sys.argv) > 2:
        with open(sys.argv[2], "r", encoding="utf-8") as f:
            return json.load(f)
    return json.load(sys.stdin)


def to_table(rows: list, columns: list[tuple[str, str]]) -> list[list]:
    return [[getattr(row, field, None) for _, field in columns] for row in rows]


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in SEARCHERS:
        raise SystemExit(f"Usage: python src/main.py <{'|'.join(SEARCHERS)}> [search.json]")

    kind = sys.argv[1]
    search_fn, columns = SEARCHERS[kind]

    try:
        search_params = read_search_json()
    except (json.JSONDecodeError, OSError) as exc:
        raise SystemExit(f"Could not read search input: {exc}")

    try:
        rows = search_fn(search_params)
    except ValidationError as exc:
        print("Invalid search parameters:", file=sys.stderr)
        for err in exc.errors():
            loc = ".".join(str(p) for p in err["loc"]) or "(top level)"
            print(f"  - {loc}: {err['msg']}", file=sys.stderr)
        raise SystemExit(1)
    except ApifyError as exc:
        print(f"Apify request failed: {exc}", file=sys.stderr)
        raise SystemExit(1)

    if not rows:
        print("No results.")
        return

    headers = [name for name, _ in columns]
    print(tabulate(to_table(rows, columns), headers=headers, tablefmt="github"))


if __name__ == "__main__":
    main()
