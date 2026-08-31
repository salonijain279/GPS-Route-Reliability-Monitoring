# Public data fixture

Run `python src/generate_sample_data.py` from the repository root to create:

- `trips.csv` — 60 synthetic trips across three routes, six devices, and two providers;
- `positions.csv` — ordered GPS pings with controlled coverage, gap, freeze, and spatial-jump failure modes;
- `route_stops.csv` — 18 synthetic planned stops used for Haversine geofence validation.

Generation is deterministic (`seed=27`) so tests and reported examples are reproducible.

No original client data, locations, identifiers, routes, providers, schools, or live-case results are included in this repository.
