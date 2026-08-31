"""Generate deterministic synthetic trip and GPS data for the public demo."""

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

ROUTE_TEMPLATES = {
    1: [
        (44.9490, -93.1090),
        (44.9560, -93.1010),
        (44.9630, -93.0940),
        (44.9710, -93.0860),
        (44.9780, -93.0790),
        (44.9860, -93.0710),
    ],
    2: [
        (44.9380, -93.1250),
        (44.9460, -93.1190),
        (44.9530, -93.1080),
        (44.9580, -93.0960),
        (44.9650, -93.0870),
        (44.9730, -93.0810),
    ],
    3: [
        (44.9220, -93.0980),
        (44.9300, -93.0910),
        (44.9390, -93.0870),
        (44.9480, -93.0820),
        (44.9560, -93.0750),
        (44.9630, -93.0670),
    ],
}


def _interpolate_route(route: list[tuple[float, float]], count: int) -> np.ndarray:
    """Sample evenly across a route's planned stop sequence."""
    progress = np.linspace(0, len(route) - 1, count)
    segment = np.minimum(progress.astype(int), len(route) - 2)
    fraction = progress - segment
    start = np.asarray(route)[segment]
    end = np.asarray(route)[segment + 1]
    return start + (end - start) * fraction[:, None]


def generate(
    seed: int = 27,
    trip_count: int = 60,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    trip_rows: list[dict] = []
    position_rows: list[dict] = []
    position_id = 1

    stop_rows = [
        {
            "route_id": route_id,
            "stop_sequence": sequence,
            "stop_id": f"route_{route_id}_stop_{sequence}",
            "stop_lat": lat,
            "stop_lng": lng,
        }
        for route_id, coordinates in ROUTE_TEMPLATES.items()
        for sequence, (lat, lng) in enumerate(coordinates, start=1)
    ]

    for trip_id in range(1, trip_count + 1):
        device_id = 1 + (trip_id - 1) % 6
        route_id = 1 + (trip_id - 1) % len(ROUTE_TEMPLATES)
        vendor_id = 1 if device_id <= 3 else 2
        polling_interval = 30 if vendor_id == 1 else 60
        duration_min = int(rng.integers(24, 46))
        expected = max(5, duration_min * 60 // polling_interval)

        # Devices 4-6 demonstrate degraded behavior in a controlled way.
        observed = expected
        if device_id == 4:
            observed = max(4, int(expected * 0.35))
        if device_id == 5:
            observed = max(8, int(expected * 0.75))
        if device_id == 6:
            observed = max(8, int(expected * 0.80))

        trip_rows.append(
            {
                "trip_id": trip_id,
                "route_id": route_id,
                "tracking_device_id": device_id,
                "vendor_id": vendor_id,
                "source": f"provider_{vendor_id}",
                "polling_interval_s": polling_interval,
                "trip_duration_min": duration_min,
            }
        )

        start_ts = 1_750_000_000 + trip_id * 7_200
        timestamps = np.linspace(
            start_ts,
            start_ts + duration_min * 60,
            num=observed,
            dtype=int,
        )
        if device_id == 5 and observed > 7:
            timestamps[observed // 2 :] += 420

        route_coordinates = _interpolate_route(ROUTE_TEMPLATES[route_id], observed)
        if device_id == 6:
            latitudes = np.repeat(route_coordinates[0, 0], observed)
            longitudes = np.repeat(route_coordinates[0, 1], observed)
        else:
            latitudes = route_coordinates[:, 0] + rng.normal(0, 0.00012, observed)
            longitudes = route_coordinates[:, 1] + rng.normal(0, 0.00012, observed)

        # Device 3 demonstrates a spatial jump that implies impossible road speed.
        if device_id == 3 and observed > 10:
            jump_index = observed // 2
            latitudes[jump_index] += 0.25
            longitudes[jump_index] += 0.25

        for timestamp, lat, lng in zip(timestamps, latitudes, longitudes):
            position_rows.append(
                {
                    "position_id": position_id,
                    "trip_id": trip_id,
                    "tracking_device_id": device_id,
                    "timestamp": int(timestamp),
                    "lat": round(float(lat), 6),
                    "lng": round(float(lng), 6),
                }
            )
            position_id += 1

    return (
        pd.DataFrame(trip_rows),
        pd.DataFrame(position_rows),
        pd.DataFrame(stop_rows),
    )


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    trips, positions, route_stops = generate()
    trips.to_csv(DATA_DIR / "trips.csv", index=False)
    positions.to_csv(DATA_DIR / "positions.csv", index=False)
    route_stops.to_csv(DATA_DIR / "route_stops.csv", index=False)
    print(
        f"Wrote {len(trips):,} trips, {len(positions):,} synthetic positions, "
        f"and {len(route_stops):,} planned stops to {DATA_DIR}"
    )


if __name__ == "__main__":
    main()
