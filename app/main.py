from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(
    title="Master Agent API",
    description="A safe starter API for a modular personal automation agent.",
    version="0.2.0",
)

# Starter-only in-memory task store. Tasks reset when the process restarts.
# Add authentication and persistent storage before exposing this API publicly.
_tasks: dict[str, dict] = {}


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    details: str = Field(default="", max_length=4000)
    task_type: Literal["echo", "word_count", "current_time"] = "echo"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


@app.get("/")
def root():
    return {
        "name": "master-agent",
        "status": "running",
        "version": app.version,
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health():
    return {"status": "ok", "timestamp": now_utc()}


@app.post("/tasks", status_code=201)
def create_task(payload: TaskCreate):
    task_id = str(uuid4())
    task = {
        "id": task_id,
        "title": payload.title,
        "details": payload.details,
        "task_type": payload.task_type,
        "status": "queued",
        "result": None,
        "error": None,
        "created_at": now_utc(),
        "started_at": None,
        "completed_at": None,
    }
    _tasks[task_id] = task
    return task


@app.get("/tasks")
def list_tasks():
    return {"items": list(_tasks.values()), "count": len(_tasks)}


@app.get("/tasks/{task_id}")
def get_task(task_id: str):
    task = _tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.post("/tasks/{task_id}/run")
def run_task(task_id: str):
    task = _tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    if task["status"] == "running":
        raise HTTPException(status_code=409, detail="Task is already running")

    task["status"] = "running"
    task["started_at"] = now_utc()
    task["error"] = None

    try:
        if task["task_type"] == "echo":
            result = {
                "message": "Task executed successfully.",
                "output": task["details"],
            }
        elif task["task_type"] == "word_count":
            words = task["details"].split()
            result = {
                "word_count": len(words),
                "character_count": len(task["details"]),
            }
        elif task["task_type"] == "current_time":
            result = {"current_time_utc": now_utc()}
        else:
            # Defensive fallback in case stored task data is unexpected.
            raise ValueError("Unsupported task type")

        task["result"] = result
        task["status"] = "completed"
        task["completed_at"] = now_utc()
    except Exception as exc:
        task["status"] = "failed"
        task["error"] = str(exc)
        task["completed_at"] = now_utc()
        raise HTTPException(status_code=500, detail="Task execution failed") from exc

    return task
