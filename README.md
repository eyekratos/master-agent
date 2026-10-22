# Master Agent

A personal AI-agent project designed to grow into a modular automation system.

## Current features

- FastAPI backend with a health endpoint
- Create, list, and inspect tasks
- Run safe built-in task types: `echo`, `word_count`, and `current_time`
- Task lifecycle fields: queued, running, completed, failed
- Interactive API docs at `/docs`
- Dockerfile and Docker Compose for local testing
- Environment-variable template for future AI provider configuration

## Run locally with Docker

Requirements: Docker Engine and Docker Compose.

```bash
docker compose up --build
```

Open:
- API status: http://127.0.0.1:8000/health
- Interactive API docs: http://127.0.0.1:8000/docs

Stop it with `Ctrl+C`, or run `docker compose down`.

## Run locally with Python

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## API endpoints

- `GET /` — service overview
- `GET /health` — health check
- `POST /tasks` — create a task
- `GET /tasks` — list tasks
- `GET /tasks/{task_id}` — inspect a task
- `POST /tasks/{task_id}/run` — execute a supported built-in task

Example create-task body:

```json
{
  "title": "Count words",
  "details": "hello from master agent",
  "task_type": "word_count"
}
```

Supported task types:
- `echo` — returns the details text
- `word_count` — counts words and characters in details
- `current_time` — returns the current UTC time

In Swagger UI, create a task with `POST /tasks`, copy the returned `id`, then use that ID in `POST /tasks/{task_id}/run`. Check the result with `GET /tasks/{task_id}`.

The task store is in memory; tasks are lost when the service restarts. These are deterministic demo tasks, not an AI model integration yet.

## Security notes

- Keep secrets and API keys in environment variables; never commit real credentials.
- The Compose configuration binds to `127.0.0.1` so the API is only exposed locally by default.
- Add authentication, authorization, rate limiting, persistent storage, and request validation before any public deployment.
- Never expose an unauthenticated task-execution endpoint to the internet.

## Roadmap

1. Add persistent task storage.
2. Add a task queue and scheduled jobs.
3. Add an AI provider adapter after choosing a provider and budget.
4. Add authentication and safe tool permissions.
5. Deploy to an available free-tier cloud service, respecting its limits.
