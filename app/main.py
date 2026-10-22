from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(
    title="Master Agent API",
    description="A small starter API for a modular personal automation agent.",
    version="0.1.0",
)

# Starter-only in-memory task store. Tasks reset when the process restarts.
# Add authentication and persistent storage before exposing this API publicly.
_tasks: dict[str, dict] = {}


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    details: str = Field(default="", max_length=4000)


@app.get("/")
def root():
    return {
        "name": "master-agent",
        "status": "running",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.post("/tasks", status_code=201)
def create_task(payload: TaskCreate):
    task_id = str(uuid4())
    task = {
        "id": task_id,
        "title": payload.title,
        "details": payload.details,
        "status": "queued",
        "created_at": datetime.now(timezone.utc).isoformat(),
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
