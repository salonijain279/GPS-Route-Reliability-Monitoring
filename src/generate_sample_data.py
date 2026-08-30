"""Generate deterministic synthetic trip and GPS data for the public demo."""

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"


def generate(seed: int = 27, trip_count: int = 60) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    trip_rows: list[dict] = []
    position_rows: list[dict] = []
    position_id = 1

    for trip_id in range(1, trip_count + 1):
        device_id = 1 + (trip_id - 1) % 6
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

        base_lat = 44.95 + rng.normal(0, 0.01)
        base_lng = -93.10 + rng.normal(0, 0.01)
        if device_id == 6:
            latitudes = np.repeat(base_lat, observed)
            longitudes = np.repeat(base_lng, observed)
        else:
            latitudes = base_lat + np.linspace(0, 0.06, observed) + rng.normal(0, 0.0002, observed)
            longitudes = base_lng + np.linspace(0, 0.04, observed) + rng.normal(0, 0.0002, observed)

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

    return pd.DataFrame(trip_rows), pd.DataFrame(position_rows)


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    trips, positions = generate()
    trips.to_csv(DATA_DIR / "trips.csv", index=False)
    positions.to_csv(DATA_DIR / "positions.csv", index=False)
    print(f"Wrote {len(trips):,} trips and {len(positions):,} synthetic positions to {DATA_DIR}")


if __name__ == "__main__":
    main()
