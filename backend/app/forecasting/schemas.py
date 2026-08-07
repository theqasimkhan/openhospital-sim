"""
Pydantic schemas for all forecasting API request and response objects.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# ── Requests ───────────────────────────────────────────────────────────────────

class ForecastRunRequest(BaseModel):
    horizon_steps: int = Field(
        default=12,
        ge=1,
        le=168,
        description=(
            "Number of simulation steps to forecast ahead. "
            "One step = step_duration_min of simulated time (default 60 min)."
        ),
    )
    step_duration_min: float = Field(
        default=60.0,
        gt=0.0,
        description="Duration of one simulation step in simulated minutes.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {"horizon_steps": 12, "step_duration_min": 60.0}
        }
    }


# ── Shared sub-models ──────────────────────────────────────────────────────────

class ForecastPointSchema(BaseModel):
    step_ahead:     int
    sim_time_ahead: float
    value:          float
    lower_ci:       float
    upper_ci:       float


class ForecastResultSchema(BaseModel):
    metric:            str
    model:             str
    data_points_used:  int
    horizon_steps:     int
    step_duration_min: float
    confidence:        float
    trend:             Literal["increasing", "decreasing", "stable", "unknown"]
    last_value:        float
    mean_forecast:     float
    points:            list[ForecastPointSchema]


class ForecastBundleSchema(BaseModel):
    run_id:                str
    sim_time_at_forecast:  float
    data_points_available: int
    horizon_steps:         int
    step_duration_min:     float
    overall_confidence:    float
    forecasts:             dict[str, ForecastResultSchema]


# ── Surge risk ────────────────────────────────────────────────────────────────

class SurgeSignals(BaseModel):
    arrival_zscore:      float   = Field(description="Z-score of recent vs baseline arrivals")
    queue_length:        int     = Field(description="Current emergency queue length")
    queue_trend:         str     = Field(description="'increasing' | 'stable' | 'decreasing'")
    icu_utilization:     float   = Field(description="Current ICU utilisation fraction")
    icu_trend:           str     = Field(description="'rising' | 'stable' | 'falling'")
    recent_spike_events: int     = Field(description="Spike events in recent history window")
    data_points:         int     = Field(description="How many steps of data are available")


class SurgeRiskResponse(BaseModel):
    simulation_time:    float
    risk_level:         Literal["low", "medium", "high", "critical"]
    risk_score:         float   = Field(description="Composite risk score in [0, 1]")
    arrival_trend:      str
    confidence:         float
    signals:            SurgeSignals
    message:            str
    recommended_actions: list[str]

    model_config = {
        "json_schema_extra": {
            "example": {
                "simulation_time":  480.0,
                "risk_level":       "medium",
                "risk_score":       0.46,
                "arrival_trend":    "increasing",
                "confidence":       0.72,
                "signals": {
                    "arrival_zscore":      1.8,
                    "queue_length":        7,
                    "queue_trend":         "increasing",
                    "icu_utilization":     0.71,
                    "icu_trend":           "rising",
                    "recent_spike_events": 1,
                    "data_points":         8,
                },
                "message":          "Moderate surge risk: arrival rate 1.8σ above baseline.",
                "recommended_actions": [
                    "Pre-position additional staff for next shift.",
                    "Review ICU bed availability.",
                ],
            }
        }
    }


# ── Optimization schemas (used by optimization API) ───────────────────────────

class OptimizationRunRequest(BaseModel):
    algorithm: Literal["greedy", "genetic", "pso"] = Field(
        default="greedy",
        description="Optimization algorithm to use.",
    )
    seed: int = Field(
        default=42,
        ge=0,
        description="Random seed for reproducibility.",
    )
    max_iterations: int = Field(
        default=60,
        ge=5,
        le=500,
        description="Maximum iterations / generations for the optimizer.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {"algorithm": "genetic", "seed": 42, "max_iterations": 60}
        }
    }


class OptimizationResultSchema(BaseModel):
    run_id:                str
    algorithm:             str
    state_simulation_time: float
    best_solution:         dict[str, float]
    best_score:            float
    baseline_score:        float
    improvement_pct:       float
    evaluations:           int
    iterations:            int
    converged:             bool
    convergence_history:   list[dict[str, Any]]
    all_objectives:        list[dict[str, Any]]
    wall_time_seconds:     float
    recommendations:       list[str]
