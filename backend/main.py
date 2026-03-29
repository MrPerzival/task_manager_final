"""
Task Management API — Production Backend
=========================================
FastAPI + SQLAlchemy  |  SQLite (dev) / PostgreSQL (prod)

Features
--------
• Full CRUD for tasks (GET / POST / PUT / DELETE)
• Task dependency: blocked_by with orphan cleanup on delete
• Circular dependency detection (DFS)
• Recurring task auto-spawn on Done transition (Daily / Weekly)
• 2-second async processing delay on create / update
• Structured logging (LOG_LEVEL env var)
• Consistent JSON error envelope  { "error": true, "detail": "..." }
• Configurable CORS (ALLOWED_ORIGINS env var)
• PostgreSQL + SQLite support via DATABASE_URL env var
• Python 3.11 compatible (avoids pydantic-core Rust build issue)
"""

import asyncio
import logging
import os
from datetime import timedelta
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from database import Base, engine, get_db
import models as db_models
import schemas

# ═════════════════════════════════════════════════════════════════════════════
# Environment & Logging
# ═════════════════════════════════════════════════════════════════════════════

load_dotenv()  # reads .env when present; no-op when env vars are already set

_log_level_name: str = os.getenv("LOG_LEVEL", "INFO").upper()
_log_level: int = getattr(logging, _log_level_name, logging.INFO)

logging.basicConfig(
    level=_log_level,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("task_manager")
logger.info("Logging initialised at level %s", _log_level_name)

# ═════════════════════════════════════════════════════════════════════════════
# App initialisation
# ═════════════════════════════════════════════════════════════════════════════

# Create all ORM tables on startup (idempotent — safe to run repeatedly).
# In production with Alembic, this is a fallback safety net.
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Task Manager API",
    description=(
        "Production-ready task management with dependencies, recurring tasks, "
        "async processing, and PostgreSQL / SQLite support."
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ═════════════════════════════════════════════════════════════════════════════
# CORS — configurable via ALLOWED_ORIGINS environment variable
# ═════════════════════════════════════════════════════════════════════════════
# Examples:
#   ALLOWED_ORIGINS=*                                      (development)
#   ALLOWED_ORIGINS=https://myapp.com,https://staging.myapp.com  (production)

_raw_origins: str = os.getenv("ALLOWED_ORIGINS", "*")

if _raw_origins.strip() == "*":
    _cors_origins: List[str] = ["*"]
    logger.warning("CORS is open to all origins — restrict ALLOWED_ORIGINS in production.")
else:
    _cors_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]
    logger.info("CORS allowed origins: %s", _cors_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ═════════════════════════════════════════════════════════════════════════════
# Global exception handlers
# ═════════════════════════════════════════════════════════════════════════════
# Both handlers return  { "error": true, "detail": "<string>" }
# so the Flutter client always gets a uniform shape — never an HTML page.


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled server errors — returns 500 with safe message."""
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": True,
            "detail": "An unexpected server error occurred. Please try again later.",
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Wraps FastAPI's HTTPException with the uniform error envelope."""
    logger.warning(
        "HTTP %s on %s %s — %s",
        exc.status_code, request.method, request.url.path, exc.detail,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": True, "detail": exc.detail},
    )


# ═════════════════════════════════════════════════════════════════════════════
# Business-logic helpers
# ═════════════════════════════════════════════════════════════════════════════


def _detect_circular_dependency(
    task_id: int,
    blocked_by_id: int,
    db: Session,
    visited: Optional[set] = None,
) -> bool:
    """
    Depth-first search through the blocked_by chain.

    Starts at blocked_by_id and follows each task's own blocked_by link
    upward. Returns True if task_id is encountered (cycle confirmed).

    Parameters
    ----------
    task_id       : ID of the task being edited — the potential cycle root.
    blocked_by_id : ID of the proposed new blocker.
    db            : Active SQLAlchemy session.
    visited       : Set of already-explored node IDs (prevents infinite loops).
    """
    if visited is None:
        visited = set()

    if blocked_by_id == task_id:
        return True  # cycle confirmed

    if blocked_by_id in visited:
        return False  # already explored, no cycle from here

    visited.add(blocked_by_id)

    blocker = (
        db.query(db_models.Task)
        .filter(db_models.Task.id == blocked_by_id)
        .first()
    )

    if blocker is None:
        return False  # chain ends — no cycle possible

    if blocker.blocked_by is not None:
        return _detect_circular_dependency(task_id, blocker.blocked_by, db, visited)

    return False


def _create_recurring_task(original: db_models.Task, db: Session) -> db_models.Task:
    """
    Spawn the next occurrence of a recurring task when the original is Done.

    Rules
    -----
    • All fields copied from original verbatim.
    • status reset to "To-Do".
    • due_date advanced by +1 day (Daily) or +7 days (Weekly).
      If due_date is None, the new task also has no due date.
    • Original task is left completely unchanged.
    """
    delta = timedelta(days=1 if original.recurring == "Daily" else 7)
    next_due = (original.due_date + delta) if original.due_date else None

    new_task = db_models.Task(
        title=original.title,
        description=original.description,
        due_date=next_due,
        status="To-Do",
        blocked_by=original.blocked_by,
        recurring=original.recurring,
    )
    db.add(new_task)
    db.commit()
    db.refresh(new_task)

    logger.info(
        "Recurring task spawned: new id=%d from original id=%d (next_due=%s)",
        new_task.id, original.id, next_due,
    )
    return new_task


# ═════════════════════════════════════════════════════════════════════════════
# Routes
# ═════════════════════════════════════════════════════════════════════════════


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/", tags=["health"])
def root():
    """Lightweight liveness probe used by Render / Docker health checks."""
    return {
        "status": "ok",
        "message": "Task Manager API is running.",
        "version": "2.0.0",
    }


# ── GET /tasks ─────────────────────────────────────────────────────────────────

@app.get("/tasks", response_model=List[schemas.TaskResponse], tags=["tasks"])
async def get_tasks(
    status: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Return all tasks with optional filters.

    Query parameters
    ----------------
    status : "To-Do" | "In Progress" | "Done"
    search : case-insensitive substring match on title
    """
    query = db.query(db_models.Task)

    if status:
        query = query.filter(db_models.Task.status == status)

    if search:
        query = query.filter(db_models.Task.title.ilike(f"%{search}%"))

    tasks = query.order_by(db_models.Task.id).all()
    logger.debug(
        "GET /tasks → %d tasks (status=%s, search=%r)", len(tasks), status, search
    )
    return tasks


# ── POST /tasks ────────────────────────────────────────────────────────────────

@app.post("/tasks", response_model=schemas.TaskResponse, status_code=201, tags=["tasks"])
async def create_task(payload: schemas.TaskCreate, db: Session = Depends(get_db)):
    """
    Create a new task.

    Validations
    -----------
    1. Title must be non-empty (enforced by Pydantic + route layer).
    2. blocked_by, if set, must reference an existing task.
    3. Self-block guard applied post-insert (ID unknown until then).

    The 2-second async sleep simulates real-world processing (notifications,
    workflow triggers etc.) without blocking the event loop.
    """
    await asyncio.sleep(2)  # non-blocking delay — event loop stays responsive

    # Validate blocked_by reference
    if payload.blocked_by is not None:
        blocker = (
            db.query(db_models.Task)
            .filter(db_models.Task.id == payload.blocked_by)
            .first()
        )
        if not blocker:
            raise HTTPException(
                status_code=404,
                detail=f"Blocking task with id={payload.blocked_by} does not exist.",
            )

    task = db_models.Task(
        title=payload.title,          # already trimmed by Pydantic validator
        description=payload.description,
        due_date=payload.due_date,
        status=payload.status,
        blocked_by=payload.blocked_by,
        recurring=payload.recurring,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # Self-block guard — can only be checked after ID is assigned
    if task.blocked_by == task.id:
        logger.warning("Self-block detected for id=%d — clearing blocked_by.", task.id)
        task.blocked_by = None
        db.commit()
        db.refresh(task)

    logger.info(
        "Task CREATED  id=%d  title=%r  status=%s  recurring=%s",
        task.id, task.title, task.status, task.recurring,
    )
    return task


# ── PUT /tasks/{task_id} ───────────────────────────────────────────────────────

@app.put("/tasks/{task_id}", response_model=schemas.TaskResponse, tags=["tasks"])
async def update_task(
    task_id: int,
    payload: schemas.TaskUpdate,
    db: Session = Depends(get_db),
):
    """
    Update an existing task (partial updates supported — only send changed fields).

    Validations
    -----------
    1. Task must exist.
    2. title (if provided) must be non-empty.
    3. blocked_by (if provided):
       a. Must not equal task's own id (self-block).
       b. Referenced task must exist.
       c. Must not create a circular dependency (DFS check).

    Recurring spawn
    ---------------
    Fires only on the Done transition (previous_status != "Done" → "Done")
    and only when recurring != "None".  Guard prevents double-spawning.
    """
    await asyncio.sleep(2)  # same non-blocking delay as create

    task = db.query(db_models.Task).filter(db_models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task id={task_id} not found.")

    # Title validation
    if payload.title is not None and not payload.title.strip():
        raise HTTPException(status_code=422, detail="Title must not be empty.")

    # blocked_by validation
    if payload.blocked_by is not None:
        if payload.blocked_by == task_id:
            raise HTTPException(status_code=422, detail="A task cannot block itself.")

        blocker = (
            db.query(db_models.Task)
            .filter(db_models.Task.id == payload.blocked_by)
            .first()
        )
        if not blocker:
            raise HTTPException(
                status_code=404,
                detail=f"Blocking task with id={payload.blocked_by} does not exist.",
            )

        if _detect_circular_dependency(task_id, payload.blocked_by, db):
            raise HTTPException(
                status_code=422,
                detail=(
                    "Circular dependency detected. "
                    "Accepting this would create a cycle in the task chain."
                ),
            )

    previous_status = task.status

    # Apply partial updates — only fields present in payload
    if payload.title       is not None: task.title       = payload.title.strip()
    if payload.description is not None: task.description = payload.description
    if payload.due_date    is not None: task.due_date    = payload.due_date
    if payload.status      is not None: task.status      = payload.status
    if payload.blocked_by  is not None: task.blocked_by  = payload.blocked_by
    if payload.recurring   is not None: task.recurring   = payload.recurring

    db.commit()
    db.refresh(task)

    logger.info(
        "Task UPDATED  id=%d  title=%r  %s→%s  recurring=%s",
        task.id, task.title, previous_status, task.status, task.recurring,
    )

    # Recurring spawn — only on Done transition
    if (
        payload.status == "Done"
        and previous_status != "Done"
        and task.recurring
        and task.recurring != "None"
    ):
        _create_recurring_task(task, db)

    return task


# ── DELETE /tasks/{task_id} ────────────────────────────────────────────────────

@app.delete("/tasks/{task_id}", status_code=204, tags=["tasks"])
def delete_task(task_id: int, db: Session = Depends(get_db)):
    """
    Delete a task permanently.

    Orphan protection: any tasks that were blocked_by this task have their
    blocked_by field cleared so they are no longer incorrectly blocked.
    """
    task = db.query(db_models.Task).filter(db_models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task id={task_id} not found.")

    orphans = (
        db.query(db_models.Task)
        .filter(db_models.Task.blocked_by == task_id)
        .update({"blocked_by": None})
    )
    if orphans:
        logger.info(
            "Cleared blocked_by for %d orphaned task(s) after deleting id=%d",
            orphans, task_id,
        )

    db.delete(task)
    db.commit()

    logger.info("Task DELETED  id=%d  title=%r", task_id, task.title)
    return None
