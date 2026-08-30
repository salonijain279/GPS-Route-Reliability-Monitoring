import sys
import unittest
from pathlib import Path

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gps_quality import build_device_health, build_trip_quality


class GPSQualityTests(unittest.TestCase):
    def setUp(self):
        self.trips = pd.DataFrame(
            [
                {"trip_id": 1, "tracking_device_id": 1, "vendor_id": 1, "polling_interval_s": 60, "trip_duration_min": 10},
                {"trip_id": 2, "tracking_device_id": 2, "vendor_id": 1, "polling_interval_s": 60, "trip_duration_min": 10},
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

    def test_frozen_device_scores_below_healthy_trip(self):
        quality = build_trip_quality(self.trips, self.positions).set_index("trip_id")
        self.assertFalse(bool(quality.loc[1, "flag_frozen"]))
        self.assertTrue(bool(quality.loc[2, "flag_frozen"]))
        self.assertGreater(quality.loc[1, "quality_score"], quality.loc[2, "quality_score"])

    def test_device_summary_preserves_trip_count(self):
        quality = build_trip_quality(self.trips, self.positions)
        health = build_device_health(quality)
        self.assertEqual(int(health["total_trips"].sum()), 2)

    def test_missing_columns_fail_fast(self):
        with self.assertRaises(ValueError):
            build_trip_quality(self.trips.drop(columns=["trip_id"]), self.positions)


if __name__ == "__main__":
    unittest.main()
