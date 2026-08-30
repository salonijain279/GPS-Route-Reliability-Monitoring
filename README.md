# Monitoring GPS Reliability for Route Operations

A Python pipeline that converts raw GPS pings into interpretable trip-quality flags and device-health scores using synthetic transportation data.

## Business question

How can an operations team distinguish a route that was executed as planned from one that only appears incomplete because its tracking device was unreliable?

## What the pipeline does

- validates trip and position schemas;
- measures ping coverage and the largest reporting gap;
- flags frozen coordinates, missing GPS, long gaps, and low coverage;
- produces a transparent 0-100 trip-quality score;
- aggregates recurring issues into a device-health report.

## Repository safety

The original academic live case used client-provided school-transportation data. **No client data, names, identifiers, routes, schools, vendors, screenshots, or internal documentation are included here.** The generator creates a small synthetic dataset solely to demonstrate the analytical workflow.

## Run

```bash
python src/generate_sample_data.py
python src/gps_quality.py
python -m unittest discover -s tests
```

Generated files:

- `data/trips.csv`
- `data/positions.csv`
- `outputs/trip_gps_quality.csv`
- `outputs/device_health_report.csv`

## Methods

`Python` · `pandas` · data validation · anomaly detection · interpretable scoring · operational analytics

## Portfolio context

This public reconstruction reflects the method developed during MSBA coursework. It is intentionally generic and is not a deployment artifact from the client environment.
