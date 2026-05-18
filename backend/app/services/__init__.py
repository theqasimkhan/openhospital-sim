"""
Services layer.

Place business-logic service classes here, one module per domain:
    services/patient_service.py
    services/department_service.py
    services/simulation_service.py
    services/analytics_service.py
    ...

Services receive a SQLAlchemy AsyncSession (and optionally a Redis client)
via their constructors and must NOT import from ``app.api`` to avoid
circular dependencies.
"""
