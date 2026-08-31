# Monitoring GPS Reliability for Route Operations

In the original academic live case, I worked with school-transportation GPS data and saw how difficult it can be to separate an operational issue from a tracking issue. For this public version, I rebuilt that analytical workflow in Python with synthetic data.

I designed the pipeline to convert raw GPS pings into interpretable trip-quality flags and device-health scores rather than hiding the decision inside one opaque model.

## Business question

How can an operations team distinguish a route that was executed as planned from one that only appears incomplete because its tracking device was unreliable?

## What I built

- validates trip and position schemas;
- measures ping coverage and the largest reporting gap;
- flags frozen coordinates, missing GPS, long gaps, and low coverage;
- produces a transparent 0-100 trip-quality score;
- aggregates recurring issues into a device-health report.

## Repository safety

I did not include any client data, names, identifiers, routes, schools, vendors, screenshots, or internal documentation from the live case. I wrote a small synthetic-data generator solely to demonstrate my analytical workflow.

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
