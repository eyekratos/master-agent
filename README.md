# Master Agent

A personal AI-agent project designed to grow into a modular automation system.

## Current starter features

- FastAPI backend with a health endpoint
- Simple in-memory task creation and listing API
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
- `POST /tasks` — create a task (JSON body: `{"title":"Example task","details":"Optional notes"}`)
- `GET /tasks` — list tasks
- `GET /tasks/{task_id}` — get one task

The task store is in memory for this starter version. Tasks are lost when the service restarts. No AI model is connected yet; this is the backend foundation.

## Security notes

- Keep secrets and API keys in environment variables; never commit real credentials.
- The Compose configuration binds to `127.0.0.1` so the API is only exposed locally by default.
- Add authentication, authorization, rate limiting, persistent storage, and request validation before any public deployment.
- Never expose an unauthenticated task-execution endpoint to the internet.

## Roadmap

1. Add a defined task runner and status lifecycle.
2. Add persistent task storage.
3. Add an AI provider adapter after choosing a provider and budget.
4. Add authentication and safe tool permissions.
5. Deploy to an available free-tier cloud service, respecting its limits.
