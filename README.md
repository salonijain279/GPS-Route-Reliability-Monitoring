# GPS Route Reliability Monitoring

**A reproducible geospatial analytics workflow for separating route-performance issues from unreliable GPS telemetry.**

This project addresses a practical school-transportation question: when a route appears incomplete, did the vehicle miss the route—or did the tracking device fail to record it correctly?

The public implementation uses deterministic synthetic data and contains no client routes, locations, identifiers, results, or deliverables.

## Approach

Reliability is analyzed at three connected levels:

1. **GPS ping quality** — schema checks, provider-specific polling expectations, missing coverage, long reporting gaps, and frozen coordinates.
2. **Spatial movement quality** — vectorized Haversine distance, path length, maximum implied speed, invalid coordinates, and impossible spatial jumps.
3. **Route execution evidence** — 175-metre stop geofences, minimum stop distance, stop completion, and observed stop order.

The trip-level signals roll into an explicit 0–100 quality score and a recurring device-health report. The rules remain visible so an operations team can inspect why a trip or device was flagged.

## Controlled demo

The synthetic fixture contains 60 trips, three planned routes, 18 stops, six devices, and two GPS providers, with a different failure pattern deliberately injected into four devices so the pipeline has known ground truth.

| Device pattern | Evidence recovered by the pipeline | Mean quality score |
|---|---:|---:|
| Healthy telemetry | Plausible movement and 100% stop completion | **100** |
| Impossible coordinate jump | Maximum implied speed above 4,000 km/h | **75** |
| Low polling coverage | 33.5% mean coverage and 80% stop completion | **80** |
| Long reporting gap | A gap longer than five minutes on every trip | **80** |
| Frozen coordinates | Zero path distance and only 16.7% stop completion | **65** |

These values describe the controlled public fixture—not the confidential live-case data.

## Analysis notebook

[`notebooks/gps_route_reliability_analysis.ipynb`](notebooks/gps_route_reliability_analysis.ipynb) walks through the decision question, synthetic data, temporal and spatial diagnostics, geofence validation, and device-level results.

The notebook and tested Python pipeline use only the synthetic fixture included in this repository.

## Repository structure

```text
notebooks/
  gps_route_reliability_analysis.ipynb  Guided, public-safe analysis
src/
  generate_sample_data.py               Deterministic routes and failure modes
  gps_quality.py                        Spatial, temporal, trip, and device metrics
tests/
  test_gps_quality.py                   Distance, anomaly, geofence, and schema tests
data/
  README.md                              Data-generation and privacy notes
```

## Run locally

```bash
python src/generate_sample_data.py
python src/gps_quality.py
python -m unittest discover -s tests -v
```

The pipeline generates:

- `data/trips.csv`, `data/positions.csv`, and `data/route_stops.csv`;
- `outputs/trip_gps_quality.csv` with trip-level temporal and spatial diagnostics;
- `outputs/stop_geofence_validation.csv` with planned-stop proximity and visits;
- `outputs/device_health_report.csv` with recurring failure rates and actions.

## Methods and tools

`Python` · `pandas` · `NumPy` · vectorized Haversine distance · GPS telemetry QA · spatial anomaly detection · geofencing · route-order validation · interpretable scoring · unit testing

## Scope

The thresholds are transparent examples, not universal operating standards. A production implementation should calibrate polling, speed, and geofence rules by provider, vehicle type, road context, and business policy.
