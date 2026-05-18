"""
Replay API endpoints.

Routes
──────
GET   /replay/runs                  – list all recorded simulation runs
GET   /replay/runs/{run_id}         – full run detail (steps, events, decisions)
GET   /replay/runs/{run_id}/export  – export run events as JSON or NDJSON
GET   /replay/runs/{run_id}/steps/{step_index} – single step detail
POST  /replay/runs/{run_id}/cursor  – open a replay cursor
POST  /replay/cursor/{cursor_id}/next  – advance cursor by one step
POST  /replay/cursor/{cursor_id}/seek  – jump cursor to step index
DELETE /replay/cursor/{cursor_id}   – close a replay cursor
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Path, Query, Response, status
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.replay.store import get_replay_store

router = APIRouter(tags=["replay"])
logger = get_logger(__name__)


# ── Schemas ────────────────────────────────────────────────────────────────────

class CursorSeekRequest(BaseModel):
    step_index: int = Field(..., ge=0, description="Zero-based step index to seek to")


# ── GET /replay/runs ───────────────────────────────────────────────────────────

@router.get(
    "/runs",
    summary="List all recorded simulation runs",
    description="Returns summary metadata for all runs, newest first.",
    status_code=status.HTTP_200_OK,
)
async def list_runs(
    limit: Annotated[int, Query(ge=1, le=50, description="Maximum runs to return")] = 20,
) -> dict[str, Any]:
    store = get_replay_store()
    runs = store.list_runs(limit=limit)
    return {
        "count":           len(runs),
        "current_run_id":  store.get_current_run_id(),
        "runs":            runs,
    }


# ── GET /replay/runs/{run_id} ──────────────────────────────────────────────────

@router.get(
    "/runs/{run_id}",
    summary="Get full run detail",
    description="Returns the complete run record including all steps, events, and decisions.",
    status_code=status.HTTP_200_OK,
)
async def get_run(
    run_id: Annotated[str, Path(description="UUID of the simulation run")],
    include_steps: Annotated[bool, Query(description="Include per-step data")] = True,
) -> dict[str, Any]:
    store = get_replay_store()
    try:
        run = store.get_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return {
        "run": run.to_dict(include_steps=include_steps),
    }


# ── GET /replay/runs/{run_id}/steps/{step_index} ──────────────────────────────

@router.get(
    "/runs/{run_id}/steps/{step_index}",
    summary="Get a single step from a run",
    status_code=status.HTTP_200_OK,
)
async def get_run_step(
    run_id: Annotated[str, Path(description="UUID of the simulation run")],
    step_index: Annotated[int, Path(ge=0, description="Zero-based step index")],
) -> dict[str, Any]:
    store = get_replay_store()
    try:
        run = store.get_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    if step_index >= len(run.steps):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Step index {step_index} out of range (run has {len(run.steps)} steps)",
        )

    return {
        "run_id":      run_id,
        "total_steps": len(run.steps),
        "step":        run.steps[step_index].to_dict(),
    }


# ── GET /replay/runs/{run_id}/export ──────────────────────────────────────────

@router.get(
    "/runs/{run_id}/export",
    summary="Export run events",
    description=(
        "Export all simulation events for the given run. "
        "Set `format=ndjson` for newline-delimited JSON (stream-friendly). "
        "Set `target=decisions` to export agent decisions instead of events."
    ),
    status_code=status.HTTP_200_OK,
)
async def export_run(
    run_id: Annotated[str, Path(description="UUID of the simulation run")],
    format: Annotated[str, Query(description="Output format: json | ndjson")] = "json",
    target: Annotated[str, Query(description="What to export: events | decisions")] = "events",
) -> Response:
    store = get_replay_store()
    try:
        run = store.get_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    if format not in ("json", "ndjson"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="format must be 'json' or 'ndjson'",
        )
    if target not in ("events", "decisions"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="target must be 'events' or 'decisions'",
        )

    if target == "decisions":
        content = run.export_decisions_json()
        media_type = "application/json"
        filename = f"run-{run_id[:8]}-decisions.json"
    elif format == "ndjson":
        content = run.export_events_ndjson()
        media_type = "application/x-ndjson"
        filename = f"run-{run_id[:8]}-events.ndjson"
    else:
        content = run.export_events_json()
        media_type = "application/json"
        filename = f"run-{run_id[:8]}-events.json"

    logger.info("export_run", run_id=run_id, format=format, target=target)

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── POST /replay/runs/{run_id}/cursor ─────────────────────────────────────────

@router.post(
    "/runs/{run_id}/cursor",
    summary="Open a replay cursor",
    description=(
        "Creates a replay cursor anchored to the given run. "
        "Use the returned cursor_id to step through the run one step at a time."
    ),
    status_code=status.HTTP_201_CREATED,
)
async def create_cursor(
    run_id: Annotated[str, Path(description="UUID of the simulation run")],
) -> dict[str, Any]:
    store = get_replay_store()
    try:
        cursor_id = store.create_cursor(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    run = store.get_run(run_id)
    logger.info("replay_cursor_created", run_id=run_id, cursor_id=cursor_id)

    return {
        "cursor_id":   cursor_id,
        "run_id":      run_id,
        "total_steps": len(run.steps),
        "position":    0,
    }


# ── POST /replay/cursor/{cursor_id}/next ──────────────────────────────────────

@router.post(
    "/cursor/{cursor_id}/next",
    summary="Advance replay cursor by one step",
    description="Returns the next step data. Returns 204 No Content when the run is exhausted.",
    status_code=status.HTTP_200_OK,
    response_model=None,
)
async def cursor_next(
    cursor_id: Annotated[str, Path(description="Cursor ID returned by open-cursor")],
) -> dict[str, Any] | Response:
    store = get_replay_store()
    try:
        step_data = store.replay_step(cursor_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    if step_data is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return {"cursor_id": cursor_id, "step": step_data}


# ── POST /replay/cursor/{cursor_id}/seek ──────────────────────────────────────

@router.post(
    "/cursor/{cursor_id}/seek",
    summary="Seek replay cursor to a specific step",
    status_code=status.HTTP_200_OK,
)
async def cursor_seek(
    cursor_id: Annotated[str, Path(description="Cursor ID")],
    body: CursorSeekRequest,
) -> dict[str, Any]:
    store = get_replay_store()
    try:
        store.seek_cursor(cursor_id, body.step_index)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    return {"cursor_id": cursor_id, "position": body.step_index}


# ── DELETE /replay/cursor/{cursor_id} ─────────────────────────────────────────

@router.delete(
    "/cursor/{cursor_id}",
    summary="Close a replay cursor",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def close_cursor(
    cursor_id: Annotated[str, Path(description="Cursor ID to close")],
) -> Response:
    store = get_replay_store()
    store.close_cursor(cursor_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
