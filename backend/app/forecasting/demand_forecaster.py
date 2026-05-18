"""
DemandForecaster – patient arrival rate projection.

Projects the number of patients arriving per simulation step using
Holt's double exponential smoothing on the `arrivals` field from
the ForecastingAgent time series.

Upgrade path
────────────
• ARIMA  : replace _fit / _predict with statsmodels ARIMA(p,d,q).fit()
• Prophet: feed df[["ds","y"]] and call model.predict(future)
• XGBoost: add lag features and call xgb.XGBRegressor().predict()
"""
from __future__ import annotations

from app.forecasting.base import BaseForecaster, TimeSeries


class DemandForecaster(BaseForecaster):
    model_name = "holt_exponential_smoothing"

    @property
    def metric_name(self) -> str:
        return "arrivals_per_step"

    def _extract(self, time_series: TimeSeries) -> list[float]:
        return [float(pt.get("arrivals", 0)) for pt in time_series]
