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
TRIP_ROUTE_COLUMNS = {"trip_id", "route_id"}
ROUTE_STOP_COLUMNS = {
    "route_id",
    "stop_id",
    "stop_sequence",
    "stop_lat",
    "stop_lng",
}

EARTH_RADIUS_KM = 6_371.0088
MAX_PLAUSIBLE_SPEED_KPH = 126.0


def _require_columns(frame: pd.DataFrame, required: set[str], name: str) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{name} is missing required columns: {missing}")


def haversine_km(
    lat_1: pd.Series,
    lng_1: pd.Series,
    lat_2: pd.Series,
    lng_2: pd.Series,
) -> pd.Series:
    """Return great-circle distance between coordinate pairs in kilometres."""
    lat_1_rad = np.radians(lat_1.astype(float))
    lng_1_rad = np.radians(lng_1.astype(float))
    lat_2_rad = np.radians(lat_2.astype(float))
    lng_2_rad = np.radians(lng_2.astype(float))
    delta_lat = lat_2_rad - lat_1_rad
    delta_lng = lng_2_rad - lng_1_rad
    a = (
        np.sin(delta_lat / 2) ** 2
        + np.cos(lat_1_rad) * np.cos(lat_2_rad) * np.sin(delta_lng / 2) ** 2
    )
    return pd.Series(
        2 * EARTH_RADIUS_KM * np.arctan2(np.sqrt(a), np.sqrt(1 - a)),
        index=lat_1.index,
    )


def add_spatial_metrics(positions: pd.DataFrame) -> pd.DataFrame:
    """Add vectorised movement and coordinate-quality metrics to GPS pings."""
    ordered = positions.sort_values(["trip_id", "timestamp"]).copy()
    ordered["gap_s"] = ordered.groupby("trip_id")["timestamp"].diff()
    ordered["previous_lat"] = ordered.groupby("trip_id")["lat"].shift()
    ordered["previous_lng"] = ordered.groupby("trip_id")["lng"].shift()

    ordered["flag_invalid_coordinate"] = ~(
        ordered["lat"].between(-90, 90) & ordered["lng"].between(-180, 180)
    )
    previous_is_valid = (
        ordered["previous_lat"].between(-90, 90)
        & ordered["previous_lng"].between(-180, 180)
    )
    valid_segment = (
        ~ordered["flag_invalid_coordinate"]
        & previous_is_valid
        & ordered["gap_s"].gt(0)
    )

    ordered["segment_distance_km"] = 0.0
    ordered.loc[valid_segment, "segment_distance_km"] = haversine_km(
        ordered.loc[valid_segment, "previous_lat"],
        ordered.loc[valid_segment, "previous_lng"],
        ordered.loc[valid_segment, "lat"],
        ordered.loc[valid_segment, "lng"],
    )
    ordered["segment_speed_kph"] = 0.0
    ordered.loc[valid_segment, "segment_speed_kph"] = (
        ordered.loc[valid_segment, "segment_distance_km"]
        / ordered.loc[valid_segment, "gap_s"]
        * 3_600
    )
    return ordered


def build_trip_quality(trips: pd.DataFrame, positions: pd.DataFrame) -> pd.DataFrame:
    _require_columns(trips, TRIP_COLUMNS, "trips")
    _require_columns(positions, POSITION_COLUMNS, "positions")

    ordered = add_spatial_metrics(positions)

    position_summary = (
        ordered.groupby("trip_id")
        .agg(
            ping_count=("position_id", "count"),
            lat_std=("lat", "std"),
            lng_std=("lng", "std"),
            max_gap_s=("gap_s", "max"),
            avg_gap_s=("gap_s", "mean"),
            path_distance_km=("segment_distance_km", "sum"),
            max_speed_kph=("segment_speed_kph", "max"),
            invalid_coordinate_count=("flag_invalid_coordinate", "sum"),
        )
        .reset_index()
    )

    quality = trips.merge(position_summary, on="trip_id", how="left")
    numeric = [
        "ping_count",
        "lat_std",
        "lng_std",
        "max_gap_s",
        "avg_gap_s",
        "path_distance_km",
        "max_speed_kph",
        "invalid_coordinate_count",
    ]
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
    quality["flag_implausible_speed"] = quality["max_speed_kph"].gt(
        MAX_PLAUSIBLE_SPEED_KPH
    )
    quality["flag_invalid_coordinate"] = quality["invalid_coordinate_count"].gt(0)

    penalty = (
        quality["flag_no_gps"].astype(int) * 40
        + quality["flag_frozen"].astype(int) * 35
        + quality["flag_long_gap"].astype(int) * 20
        + quality["flag_low_coverage"].astype(int) * 20
        + quality["flag_implausible_speed"].astype(int) * 25
        + quality["flag_invalid_coordinate"].astype(int) * 40
    )
    quality["quality_score"] = (100 - penalty).clip(lower=0)
    quality["quality_label"] = pd.cut(
        quality["quality_score"],
        bins=[-np.inf, 49, 69, 84, np.inf],
        labels=["critical", "degraded", "monitor", "healthy"],
    ).astype(str)
    return quality.sort_values("trip_id").reset_index(drop=True)


def build_stop_validation(
    trips: pd.DataFrame,
    positions: pd.DataFrame,
    route_stops: pd.DataFrame,
    geofence_radius_m: float = 175.0,
) -> pd.DataFrame:
    """Match GPS pings to planned route stops with a Haversine geofence."""
    _require_columns(trips, TRIP_ROUTE_COLUMNS, "trips")
    _require_columns(positions, POSITION_COLUMNS, "positions")
    _require_columns(route_stops, ROUTE_STOP_COLUMNS, "route_stops")

    planned = trips[["trip_id", "route_id"]].merge(route_stops, on="route_id")
    candidates = planned.merge(
        positions[["trip_id", "timestamp", "lat", "lng"]],
        on="trip_id",
        how="left",
    )
    candidates["distance_m"] = (
        haversine_km(
            candidates["stop_lat"],
            candidates["stop_lng"],
            candidates["lat"],
            candidates["lng"],
        )
        * 1_000
    )
    candidates["inside_geofence"] = candidates["distance_m"].le(geofence_radius_m)
    candidates["visit_timestamp"] = candidates["timestamp"].where(
        candidates["inside_geofence"]
    )

    stop_validation = (
        candidates.groupby(
            ["trip_id", "route_id", "stop_id", "stop_sequence"],
            as_index=False,
        )
        .agg(
            minimum_distance_m=("distance_m", "min"),
            first_visit_timestamp=("visit_timestamp", "min"),
        )
        .sort_values(["trip_id", "stop_sequence"])
        .reset_index(drop=True)
    )
    stop_validation["visited"] = stop_validation["minimum_distance_m"].le(
        geofence_radius_m
    )
    stop_validation["geofence_radius_m"] = geofence_radius_m
    return stop_validation


def _route_order_score(stops: pd.DataFrame) -> float:
    visited = stops.loc[stops["visited"]].sort_values("first_visit_timestamp")
    sequence = visited["stop_sequence"].to_numpy()
    if len(sequence) < 2:
        return np.nan
    inversions = sum(
        sequence[left] > sequence[right]
        for left in range(len(sequence))
        for right in range(left + 1, len(sequence))
    )
    maximum_inversions = len(sequence) * (len(sequence) - 1) / 2
    return float(1 - inversions / maximum_inversions)


def summarize_route_validation(stop_validation: pd.DataFrame) -> pd.DataFrame:
    """Summarize geofence completion and observed stop order at trip level."""
    grouped = stop_validation.groupby(["trip_id", "route_id"], sort=True)
    summary = grouped.agg(
        planned_stop_count=("stop_id", "count"),
        visited_stop_count=("visited", "sum"),
        mean_minimum_stop_distance_m=("minimum_distance_m", "mean"),
    ).reset_index()
    summary["stop_completion_pct"] = (
        summary["visited_stop_count"] / summary["planned_stop_count"] * 100
    )
    order = pd.DataFrame(
        [
            {
                "trip_id": trip_id,
                "route_id": route_id,
                "route_order_score": _route_order_score(stops),
            }
            for (trip_id, route_id), stops in grouped
        ]
    )
    summary = summary.merge(order, on=["trip_id", "route_id"])
    return summary.sort_values("trip_id").reset_index(drop=True)


def build_device_health(trip_quality: pd.DataFrame) -> pd.DataFrame:
    flag_columns = [
        "flag_no_gps",
        "flag_frozen",
        "flag_long_gap",
        "flag_low_coverage",
        "flag_implausible_speed",
        "flag_invalid_coordinate",
    ]
    grouped = trip_quality.groupby(["tracking_device_id", "vendor_id"])
    health = grouped.agg(
        total_trips=("trip_id", "count"),
        mean_quality_score=("quality_score", "mean"),
        mean_ping_coverage_pct=("ping_coverage_pct", "mean"),
        mean_path_distance_km=("path_distance_km", "mean"),
        max_observed_speed_kph=("max_speed_kph", "max"),
    ).reset_index()

    for flag in flag_columns:
        rate = grouped[flag].mean().mul(100).rename(f"pct_{flag.removeprefix('flag_')}")
        health = health.merge(rate.reset_index(), on=["tracking_device_id", "vendor_id"])

    for metric in ["stop_completion_pct", "route_order_score"]:
        if metric in trip_quality.columns:
            device_metric = grouped[metric].mean().rename(f"mean_{metric}")
            health = health.merge(
                device_metric.reset_index(),
                on=["tracking_device_id", "vendor_id"],
            )

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
    route_stops = pd.read_csv(args.data_dir / "route_stops.csv")
    trip_quality = build_trip_quality(trips, positions)
    stop_validation = build_stop_validation(trips, positions, route_stops)
    route_validation = summarize_route_validation(stop_validation)
    trip_quality = trip_quality.merge(route_validation, on=["trip_id", "route_id"])
    device_health = build_device_health(trip_quality)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    trip_quality.to_csv(args.output_dir / "trip_gps_quality.csv", index=False)
    stop_validation.to_csv(args.output_dir / "stop_geofence_validation.csv", index=False)
    device_health.to_csv(args.output_dir / "device_health_report.csv", index=False)
    print(device_health.to_string(index=False))


if __name__ == "__main__":
    main()
