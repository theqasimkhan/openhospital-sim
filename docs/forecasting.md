# Forecasting Pipeline

## Overview

The forecasting layer provides statistical demand predictions, capacity saturation warnings, and composite surge risk assessment. All forecasters operate on live simulation data collected by the `ForecastingAgent`.

---

## Data Source

`ForecastingAgent` records one data point per simulation step:

```
step → arrivals, icu_util, ward_util, queue_length, discharges, deaths,
       doctor_workload, nurse_workload
```

The forecasting pipeline reads this time-series via:

```http
GET /api/v1/agents/forecast/timeseries
```

---

## Statistical Model: Holt's Double Exponential Smoothing

All forecasters use a shared `BaseForecaster` that implements Holt's method:

```
Level:  L(t) = α × y(t) + (1 − α) × (L(t-1) + T(t-1))
Trend:  T(t) = β × (L(t) − L(t-1)) + (1 − β) × T(t-1)
Forecast: ŷ(t+h) = L(t) + h × T(t)
```

**Confidence scaling**: Scales from `0.40` at 3 data points to `0.90` at 20+ data points. This prevents overconfident forecasts early in a run.

**Drop-in replacement**: Any `BaseForecaster` subclass can replace the default model. Examples:

```python
# Replace with Facebook Prophet (add prophet>=1.1.5 to requirements.txt)
from prophet import Prophet
class ProphetDemandForecaster(BaseForecaster):
    def _fit_predict(self, history, horizon):
        ...

# Replace with ARIMA (add statsmodels>=0.14.0)
from statsmodels.tsa.arima.model import ARIMA
class ArimaDemandForecaster(BaseForecaster):
    ...
```

---

## Forecasters

### DemandForecaster
**Metric**: Patient arrivals per step  
**Outputs**: `forecast_points` (horizon), `trend_direction` (decreasing/stable/increasing/surge)

```json
{
  "forecaster": "DemandForecaster",
  "metric": "patient_arrivals",
  "horizon_steps": 6,
  "forecast_points": [
    {"step_offset": 1, "value": 8.3, "lower": 6.1, "upper": 10.5, "confidence": 0.82},
    ...
  ],
  "trend_direction": "increasing"
}
```

### ICUForecaster
**Metric**: ICU bed utilisation fraction (0.0–1.0)  
**Extras**: `steps_to_saturation`, `saturation_probability`

```json
{
  "forecaster": "ICUForecaster",
  "metric": "icu_utilization",
  "steps_to_saturation": 4,
  "saturation_probability": 0.72,
  "forecast_points": [...]
}
```

`steps_to_saturation` is computed by finding the first step where the forecast exceeds 0.95. Returns `null` if saturation is not predicted within the horizon.

### WardUtilizationForecaster
**Metric**: Regular ward occupancy fraction  
**Outputs**: `forecast_points`, `trend_direction`

### StaffingForecaster
**Metric**: Recommended doctors and nurses for upcoming steps  
**Outputs**: `recommended_doctors`, `recommended_nurses`, `peak_staffing_required`

Staffing recommendations are derived by inverting the workload model:

```
recommended_doctors = ceil(predicted_ward_occupancy / target_workload_ratio)
recommended_nurses  = ceil((predicted_icu + predicted_ward) / target_workload_ratio)
```

---

## Surge Detector

`SurgeDetector` produces a composite risk assessment from four independent signals:

| Signal | Weight | Source |
|--------|--------|--------|
| Arrival rate anomaly | 0.35 | Current arrivals vs. 5-step moving average |
| ICU pressure | 0.30 | Current ICU occupancy ratio |
| Emergency queue | 0.20 | Queue length vs. threshold |
| Forecast trend | 0.15 | ForecastingAgent demand trend |

**Risk levels**:

| Score | Level | Recommended Action |
|-------|-------|-------------------|
| 0.0–0.3 | `low` | Normal operations |
| 0.3–0.6 | `medium` | Pre-activate surge protocol |
| 0.6–0.8 | `high` | Activate surge protocol, call extra staff |
| 0.8–1.0 | `critical` | Full emergency response |

---

## ForecastBundle

`POST /api/v1/forecasting/run` returns a `ForecastBundle` containing all four forecasters' results plus surge risk:

```json
{
  "run_at_sim_time": 480.0,
  "data_points_used": 8,
  "demand":  { ... DemandForecaster result ... },
  "icu":     { ... ICUForecaster result ... },
  "ward":    { ... WardUtilizationForecaster result ... },
  "staffing":{ ... StaffingForecaster result ... },
  "surge_risk": {
    "risk_level": "medium",
    "composite_score": 0.47,
    "signals": { "arrival_anomaly": 0.55, "icu_pressure": 0.40, ... },
    "recommended_actions": ["Pre-position additional staff", ...]
  }
}
```

---

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/forecasting/run` | Fit all forecasters; returns ForecastBundle |
| `GET` | `/api/v1/forecasting/latest` | Latest cached ForecastBundle |
| `GET` | `/api/v1/forecasting/surge-risk` | Real-time surge risk (uses latest forecast if available) |

### Run parameters

```json
POST /api/v1/forecasting/run
{
  "horizon_steps": 12,
  "alpha": 0.3,
  "beta": 0.1
}
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `horizon_steps` | 8 | How many steps ahead to forecast |
| `alpha` | 0.3 | Level smoothing factor (0 < α < 1) |
| `beta` | 0.1 | Trend smoothing factor (0 < β < 1) |

**Minimum data requirement**: 3 completed simulation steps. Returns a 422 error if insufficient data exists.
