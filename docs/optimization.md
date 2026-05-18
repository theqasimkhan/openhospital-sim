# Resource Optimization Engine

## Overview

The optimization engine finds the best allocation of hospital resources (doctors, nurses, beds) to maximise patient outcomes given the current simulation state. Three algorithms are available and can be compared directly.

---

## Decision Variables

| Variable | Range | Description |
|----------|-------|-------------|
| `doctors_on_duty` | [1, max_doctors] | Active physician count |
| `nurses_on_duty` | [1, max_nurses] | Active nurse count |
| `icu_beds_active` | [1, total_icu_beds] | Staffed ICU beds |
| `regular_beds_active` | [1, total_regular_beds] | Open ward beds |

All variables are continuous during optimisation and rounded to integers for the final solution.

---

## Objective Function

`SolutionEvaluator` computes a single scalar score from five weighted sub-objectives:

| Objective | Weight | Direction | Formula |
|-----------|--------|-----------|---------|
| Patient throughput | 0.30 | Maximize | `discharged / total_arrivals` |
| Mortality rate | 0.25 | Minimize | `1 − (deaths / total_arrivals)` |
| Resource utilisation | 0.20 | Balance | Penalises over/under utilisation |
| Staff workload equity | 0.15 | Minimize variance | Low variance across roles |
| Queue length | 0.10 | Minimize | `1 / (1 + queue_length)` |

**Composite score = Σ (weight × objective)** — higher is better, range [0.0, 1.0].

The **baseline score** evaluates the current simulation state without changes. `improvement_pct` compares the best solution to the baseline.

---

## Algorithms

### Greedy Optimizer (`algorithm: "greedy"`)

Coordinate descent with random restarts.

1. Start from the current allocation
2. For each variable in turn, try small perturbations (±1, ±2, ±5 units)
3. Accept any improvement; move to the next variable
4. Repeat for N passes (default 10)
5. Restart from a random point; keep the global best

**Wall time**: < 5 ms — suitable for every-step calls.  
**Best for**: Real-time suggestions; works well when the landscape is convex.

---

### Genetic Algorithm (`algorithm: "genetic"`)

Real-valued GA with tournament selection, BLX-α crossover, and Gaussian mutation.

| Hyperparameter | Default | Range |
|----------------|---------|-------|
| `population_size` | 30 | 10–200 |
| `max_iterations` | 60 | 10–500 |
| `crossover_rate` | 0.85 | 0–1 |
| `mutation_rate` | 0.15 | 0–1 |
| `mutation_sigma` | 0.1 | > 0 |
| `tournament_size` | 3 | 2–10 |
| `elite_fraction` | 0.1 | 0–0.5 |

**Wall time**: < 20 ms.  
**Best for**: Multi-modal fitness landscapes; avoids local optima.

---

### Particle Swarm Optimizer (`algorithm: "pso"`)

Standard PSO with inertia weight and velocity clamping.

| Hyperparameter | Default | Range |
|----------------|---------|-------|
| `n_particles` | 20 | 5–200 |
| `max_iterations` | 60 | 10–500 |
| `inertia` | 0.7 | 0–1 |
| `cognitive` | 1.5 | > 0 |
| `social` | 1.5 | > 0 |
| `max_velocity_fraction` | 0.2 | 0–1 |

**Wall time**: < 20 ms.  
**Best for**: Smooth continuous spaces; often fastest to converge.

---

## OptimizationResult Schema

```json
{
  "algorithm": "genetic",
  "best_score": 0.847,
  "baseline_score": 0.721,
  "improvement_pct": 17.5,
  "best_solution": {
    "doctors_on_duty": 18,
    "nurses_on_duty": 43,
    "icu_beds_active": 22,
    "regular_beds_active": 85
  },
  "objective_breakdown": {
    "throughput": 0.91,
    "mortality": 0.96,
    "utilisation": 0.78,
    "workload_equity": 0.82,
    "queue": 0.73
  },
  "convergence_history": [0.721, 0.733, 0.769, ...],
  "evaluations": 1800,
  "wall_time_seconds": 0.014,
  "recommendations": [
    "Increase doctors on duty from 15 to 18 (+3)",
    "Activate 2 additional ICU beds",
    "Current nurse count is adequate"
  ]
}
```

---

## API Reference

```http
POST /api/v1/optimization/run
{
  "algorithm": "genetic",
  "max_iterations": 80,
  "population_size": 40
}
```

```http
GET /api/v1/optimization/results
```

---

## Algorithm Comparison Workflow

To compare all three algorithms on the same simulation state:

```bash
# Run all three sequentially
curl -X POST localhost:8000/api/v1/optimization/run \
  -d '{"algorithm": "greedy"}' | jq .best_score

curl -X POST localhost:8000/api/v1/optimization/run \
  -d '{"algorithm": "genetic", "max_iterations": 100}' | jq .best_score

curl -X POST localhost:8000/api/v1/optimization/run \
  -d '{"algorithm": "pso", "max_iterations": 100}' | jq .best_score
```

All three share the same `SolutionEvaluator`, so scores are directly comparable.

---

## Adding a Custom Optimizer

Subclass `BaseOptimizer` in `backend/app/optimization/base.py`:

```python
class MyOptimizer(BaseOptimizer):
    def optimize(self, state_snapshot: dict) -> OptimizationResult:
        # 1. Build the search space from self.variables
        # 2. Evaluate candidates with self.evaluator.score(solution, state)
        # 3. Return OptimizationResult(...)
        ...
```

Register it in the `optimization.py` endpoint's algorithm registry.
