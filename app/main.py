import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

app = FastAPI(
    title="Master Agent API",
    description="A safe starter API with a browser-based AI chat dashboard and persistent conversation memory.",
    version="0.5.0",
)

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
DASHBOARD_FILE = BASE_DIR / "static" / "index.html"
DATA_DIR = Path(os.getenv("MASTER_AGENT_DATA_DIR", str(PROJECT_DIR / "data")))
DATABASE_FILE = DATA_DIR / "master_agent.sqlite3"

# Starter-only in-memory task store. Tasks reset when the process restarts.
# Keep this API bound to localhost until authentication is added.
_tasks: dict[str, dict] = {}


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    details: str = Field(default="", max_length=4000)
    task_type: Literal["echo", "word_count", "current_time"] = "echo"


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    conversation_id: str | None = None


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def db_connection():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_FILE, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        yield connection
        connection.commit()
    finally:
        connection.close()


def init_database() -> None:
    with db_connection() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, id)")


@app.on_event("startup")
def startup() -> None:
    init_database()


def create_conversation(first_message: str = "New conversation") -> str:
    conversation_id = str(uuid4())
    stamp = now_utc()
    title = " ".join(first_message.split())[:55] or "New conversation"
    with db_connection() as db:
        db.execute(
            "INSERT INTO conversations(id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (conversation_id, title, stamp, stamp),
        )
    return conversation_id


@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(DASHBOARD_FILE)


@app.get("/health")
def health():
    with db_connection() as db:
        db.execute("SELECT 1")
    return {"status": "ok", "memory": "sqlite", "timestamp": now_utc()}


@app.post("/conversations", status_code=201)
def new_conversation():
    conversation_id = create_conversation()
    with db_connection() as db:
        row = db.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
    return dict(row)


@app.get("/conversations")
def list_conversations():
    with db_connection() as db:
        rows = db.execute(
            "SELECT c.id, c.title, c.created_at, c.updated_at, "
            "(SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) AS message_count "
            "FROM conversations c ORDER BY c.updated_at DESC LIMIT 100"
        ).fetchall()
    return {"items": [dict(row) for row in rows]}


@app.get("/conversations/{conversation_id}/messages")
def get_conversation_messages(conversation_id: str):
    with db_connection() as db:
        conversation = db.execute(
            "SELECT id FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        rows = db.execute(
            "SELECT id, role, content, created_at FROM messages "
            "WHERE conversation_id = ? ORDER BY id",
            (conversation_id,),
        ).fetchall()
    return {"conversation_id": conversation_id, "items": [dict(row) for row in rows]}


@app.post("/chat")
def chat(payload: ChatRequest):
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="AI is not configured. Set GEMINI_API_KEY in your local .env file and restart the service.",
        )

    conversation_id = payload.conversation_id
    if conversation_id:
        with db_connection() as db:
            existing = db.execute(
                "SELECT id FROM conversations WHERE id = ?", (conversation_id,)
            ).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Conversation not found. Start a new conversation.")
    else:
        conversation_id = create_conversation(payload.message)

    # Fetch the existing history before storing this turn. Keep the latest 12
    # messages to provide useful context without growing requests indefinitely.
    with db_connection() as db:
        history_rows = db.execute(
            "SELECT role, content FROM messages WHERE conversation_id = ? "
            "ORDER BY id DESC LIMIT 12",
            (conversation_id,),
        ).fetchall()
        history_rows = list(reversed(history_rows))
        db.execute(
            "INSERT INTO messages(conversation_id, role, content, created_at) VALUES (?, 'user', ?, ?)",
            (conversation_id, payload.message, now_utc()),
        )

    model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
    try:
        from google import genai
        from google.genai import types

        contents = [
            types.Content(
                role="model" if row["role"] == "assistant" else "user",
                parts=[types.Part.from_text(text=row["content"])],
            )
            for row in history_rows
        ]
        contents.append(
            types.Content(role="user", parts=[types.Part.from_text(text=payload.message)])
        )
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(model=model, contents=contents)
        answer = (response.text or "").strip()
        if not answer:
            raise HTTPException(status_code=502, detail="The AI model returned an empty response.")
        with db_connection() as db:
            db.execute(
                "INSERT INTO messages(conversation_id, role, content, created_at) VALUES (?, 'assistant', ?, ?)",
                (conversation_id, answer, now_utc()),
            )
            db.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now_utc(), conversation_id),
            )
        return {
            "provider": "google-gemini",
            "model": model,
            "answer": answer,
            "conversation_id": conversation_id,
        }
    except HTTPException:
        raise
    except Exception as exc:
        # Keep provider details and credentials out of API responses.
        print(f"Gemini request failed: {type(exc).__name__}")
        raise HTTPException(
            status_code=502,
            detail="Gemini request failed. Check the API key, model name, network connection, and provider quota.",
        ) from exc


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
            result = {"message": "Task executed successfully.", "output": task["details"]}
        elif task["task_type"] == "word_count":
            words = task["details"].split()
            result = {"word_count": len(words), "character_count": len(task["details"])}
        elif task["task_type"] == "current_time":
            result = {"current_time_utc": now_utc()}
        else:
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
