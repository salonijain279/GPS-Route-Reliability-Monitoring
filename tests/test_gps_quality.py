import sys
import unittest
from pathlib import Path

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gps_quality import (
    build_device_health,
    build_stop_validation,
    build_trip_quality,
    haversine_km,
    summarize_route_validation,
)


class GPSQualityTests(unittest.TestCase):
    def setUp(self):
        self.trips = pd.DataFrame(
            [
                {
                    "trip_id": 1,
                    "route_id": 1,
                    "tracking_device_id": 1,
                    "vendor_id": 1,
                    "polling_interval_s": 60,
                    "trip_duration_min": 10,
                },
                {
                    "trip_id": 2,
                    "route_id": 1,
                    "tracking_device_id": 2,
                    "vendor_id": 1,
                    "polling_interval_s": 60,
                    "trip_duration_min": 10,
                },
            ]
        )
        self.positions = pd.DataFrame(
            [
                {"position_id": i + 1, "trip_id": 1, "tracking_device_id": 1, "timestamp": 1000 + i * 60, "lat": 44.0 + i * 0.001, "lng": -93.0 + i * 0.001}
                for i in range(10)
            ]
            + [
                {"position_id": 20 + i, "trip_id": 2, "tracking_device_id": 2, "timestamp": 2000 + i * 60, "lat": 45.0, "lng": -94.0}
                for i in range(10)
            ]
        )
        self.route_stops = pd.DataFrame(
            [
                {
                    "route_id": 1,
                    "stop_id": "start",
                    "stop_sequence": 1,
                    "stop_lat": 44.0,
                    "stop_lng": -93.0,
                },
                {
                    "route_id": 1,
                    "stop_id": "end",
                    "stop_sequence": 2,
                    "stop_lat": 44.009,
                    "stop_lng": -92.991,
                },
            ]
        )

    def test_frozen_device_scores_below_healthy_trip(self):
        quality = build_trip_quality(self.trips, self.positions).set_index("trip_id")
        self.assertFalse(bool(quality.loc[1, "flag_frozen"]))
        self.assertTrue(bool(quality.loc[2, "flag_frozen"]))
        self.assertGreater(quality.loc[1, "quality_score"], quality.loc[2, "quality_score"])

    def test_device_summary_preserves_trip_count(self):
        quality = build_trip_quality(self.trips, self.positions)
        health = build_device_health(quality)
        self.assertEqual(int(health["total_trips"].sum()), 2)

    def test_haversine_distance_is_geographically_plausible(self):
        distance = haversine_km(
            pd.Series([0.0]),
            pd.Series([0.0]),
            pd.Series([0.0]),
            pd.Series([1.0]),
        ).iloc[0]
        self.assertAlmostEqual(distance, 111.2, delta=0.2)

    def test_implausible_coordinate_jump_is_flagged(self):
        jumped = self.positions.loc[self.positions["trip_id"].eq(1)].copy()
        jumped.loc[jumped.index[5], ["lat", "lng"]] = [45.0, -92.0]
        quality = build_trip_quality(self.trips.iloc[[0]], jumped).iloc[0]
        self.assertTrue(bool(quality["flag_implausible_speed"]))
        self.assertGreater(quality["max_speed_kph"], 126)

    def test_geofence_validation_measures_completion_and_order(self):
        stop_validation = build_stop_validation(
            self.trips.iloc[[0]],
            self.positions.loc[self.positions["trip_id"].eq(1)],
            self.route_stops,
        )
        route_summary = summarize_route_validation(stop_validation).iloc[0]
        self.assertEqual(int(route_summary["visited_stop_count"]), 2)
        self.assertEqual(float(route_summary["stop_completion_pct"]), 100.0)
        self.assertEqual(float(route_summary["route_order_score"]), 1.0)

    def test_missing_columns_fail_fast(self):
        with self.assertRaises(ValueError):
            build_trip_quality(self.trips.drop(columns=["trip_id"]), self.positions)


if __name__ == "__main__":
    unittest.main()
