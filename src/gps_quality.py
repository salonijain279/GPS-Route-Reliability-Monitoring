"""Build transparent trip- and device-level GPS quality metrics."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

TRIP_COLUMNS = {
    "trip_id",
    "tracking_device_id",
    "vendor_id",
    "polling_interval_s",
    "trip_duration_min",
}
POSITION_COLUMNS = {
    "position_id",
    "trip_id",
    "tracking_device_id",
    "timestamp",
    "lat",
    "lng",
}


def _require_columns(frame: pd.DataFrame, required: set[str], name: str) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{name} is missing required columns: {missing}")


def build_trip_quality(trips: pd.DataFrame, positions: pd.DataFrame) -> pd.DataFrame:
    _require_columns(trips, TRIP_COLUMNS, "trips")
    _require_columns(positions, POSITION_COLUMNS, "positions")

    ordered = positions.sort_values(["trip_id", "timestamp"]).copy()
    ordered["gap_s"] = ordered.groupby("trip_id")["timestamp"].diff()

    position_summary = (
        ordered.groupby("trip_id")
        .agg(
            ping_count=("position_id", "count"),
            lat_std=("lat", "std"),
            lng_std=("lng", "std"),
            max_gap_s=("gap_s", "max"),
            avg_gap_s=("gap_s", "mean"),
        )
        .reset_index()
    )

    quality = trips.merge(position_summary, on="trip_id", how="left")
    numeric = ["ping_count", "lat_std", "lng_std", "max_gap_s", "avg_gap_s"]
    quality[numeric] = quality[numeric].fillna(0)
    quality["expected_pings"] = (
        quality["trip_duration_min"] * 60 / quality["polling_interval_s"].clip(lower=1)
    )
    quality["ping_coverage_pct"] = (
        quality["ping_count"] / quality["expected_pings"].clip(lower=1) * 100
    ).clip(upper=200)

    quality["flag_no_gps"] = quality["ping_count"].eq(0)
    quality["flag_frozen"] = (
        quality["ping_count"].ge(5)
        & quality["lat_std"].lt(0.00001)
        & quality["lng_std"].lt(0.00001)
    )
    quality["flag_long_gap"] = quality["max_gap_s"].gt(300)
    quality["flag_low_coverage"] = quality["ping_coverage_pct"].lt(50)

    penalty = (
        quality["flag_no_gps"].astype(int) * 40
        + quality["flag_frozen"].astype(int) * 35
        + quality["flag_long_gap"].astype(int) * 20
        + quality["flag_low_coverage"].astype(int) * 20
    )
    quality["quality_score"] = (100 - penalty).clip(lower=0)
    quality["quality_label"] = pd.cut(
        quality["quality_score"],
        bins=[-np.inf, 49, 69, 84, np.inf],
        labels=["critical", "degraded", "monitor", "healthy"],
    ).astype(str)
    return quality.sort_values("trip_id").reset_index(drop=True)


def build_device_health(trip_quality: pd.DataFrame) -> pd.DataFrame:
    flag_columns = [
        "flag_no_gps",
        "flag_frozen",
        "flag_long_gap",
        "flag_low_coverage",
    ]
    grouped = trip_quality.groupby(["tracking_device_id", "vendor_id"])
    health = grouped.agg(
        total_trips=("trip_id", "count"),
        mean_quality_score=("quality_score", "mean"),
        mean_ping_coverage_pct=("ping_coverage_pct", "mean"),
    ).reset_index()

    for flag in flag_columns:
        rate = grouped[flag].mean().mul(100).rename(f"pct_{flag.removeprefix('flag_')}")
        health = health.merge(rate.reset_index(), on=["tracking_device_id", "vendor_id"])

    health["device_status"] = pd.cut(
        health["mean_quality_score"],
        bins=[-np.inf, 49, 69, 84, np.inf],
        labels=["replace_or_recalibrate", "degraded", "monitor", "healthy"],
    ).astype(str)
    return health.sort_values(["mean_quality_score", "tracking_device_id"]).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs")
    args = parser.parse_args()

    trips = pd.read_csv(args.data_dir / "trips.csv")
    positions = pd.read_csv(args.data_dir / "positions.csv")
    trip_quality = build_trip_quality(trips, positions)
    device_health = build_device_health(trip_quality)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    trip_quality.to_csv(args.output_dir / "trip_gps_quality.csv", index=False)
    device_health.to_csv(args.output_dir / "device_health_report.csv", index=False)
    print(device_health.to_string(index=False))


if __name__ == "__main__":
    main()
