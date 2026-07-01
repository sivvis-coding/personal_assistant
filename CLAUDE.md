# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Run locally

```bash
cp .env.example .env
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend API docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

Backend source (`backend/app/`) and frontend source (`frontend/src/`) are hot-reloaded via Docker volume mounts.

### Backend tests

Run from the `backend/` directory or inside the backend container:

```bash
cd backend && pytest
# single test file
pytest tests/test_clickup_approval_flow.py
# single test by name
pytest tests/test_clickup_approval_flow.py::test_name
```

`asyncio_mode = "auto"` is set in `pyproject.toml`, so async test functions work without decorators. Tests under `_unused/` are excluded by `norecursedirs`.

### Frontend

```bash
cd frontend && npm install && npm run dev    # dev server
npm run build                               # tsc + vite build
```

## Architecture

### Stack

- **Backend**: Python 3.12, FastAPI, Motor (async MongoDB), Pydantic v2, OpenAI SDK, LangChain, APScheduler, dependency-injector
- **Frontend**: React 18, Vite, TypeScript, MUI v5, Zustand, Axios, React Router v6
- **Database**: MongoDB (local cache and audit log — not the source of truth for external systems)
- **Auth**: `X-Local-App-Key` header checked against `LOCAL_APP_API_KEY` env var

### Execution path (ADR-001)

Only one active execution path exists — the **direct-call backbone**:

```
HTTP request
  -> app/api/*.py (FastAPI routes + deps.py Depends factories)
  -> AssistantConversationService / TicketService / ...
  -> Tools (ToolInterface / ToolRegistry) or direct service calls
  -> Repositories -> MongoDB
     Integrations -> Freshservice / ClickUp / OpenAI
```

There is a **quarantined event-driven stack** (`app/_unused/`, `app/domain/*/events.py`, parts of `app/core/events/`) that is intentionally broken and non-functional. Do not extend or revive it — see `docs/adr/001-single-architecture-backbone.md` for context.

### Dependency injection

`app/core/di/container.py` is the single DI root. All singletons (clients, repositories, services, agents, tools) are declared there using `dependency-injector`. `bootstrap()` wires the tool registry and starts the scheduler. API routes get dependencies via `app/api/deps.py` (FastAPI `Depends` factories that read from `app.state`).

### Settings

`app/core/config.py` — `Settings` loads from `.env` via pydantic-settings. At startup, `AppSettingsRepository` reads any database overrides and merges them, making database values take precedence over env vars. Missing credential values (empty strings) intentionally disable integrations and enable mock responses rather than raising errors.

### Tool pattern

Every external action is a `ToolInterface` (`app/tools/base.py`). Tools expose an `execute(operation, **kwargs)` method and return a `ToolResult`. The `ToolRegistry` holds all registered tools; agents resolve tools by name at runtime.

### HITL approval gate

**ClickUp task creation is always two-phase:**

1. `prepare` — generates an AI user-story draft, persists it to `AiDraftRepository`, records a `WorkflowRunRepository` audit entry.
2. `approve` — only after explicit user approval creates the ClickUp task.

The assistant agent flow adds another layer: a `prepare_clickup_task` `AssistantAction` (status `proposed`) is created first. Approving it triggers `prepare`, which generates a draft and a second `approve_clickup_task` action. Approving that runs the actual `approve` step.

**Freshservice replies are never sent automatically.** `FreshClient.add_reply()` is reserved for future explicit invocation only.

### Ticket → ClickUp link deduplication

`IntegrationLinkRepository` tracks ticket-to-task links. The canonical `relation_type` is defined in `app/domain/integration_link/value_objects.py` (`RelationType.TICKET_TO_TASK`). All code reading or writing this link must import from there — no inline string literals.

### Agents

Agents live in `app/agents/` and follow the `BaseAgent` contract (`app/agents/base.py`). They call services or tools directly and return results. The conversational assistant (`app/assistant/conversation_service.py`) routes messages:

- Time tracking keywords → `TimeAgent`
- Pending client clarification state → `_handle_client_confirmation`
- Everything else → `ConversationAgent` (LLM-backed)

### Scheduler

`app/infrastructure/scheduler/` — APScheduler wraps cron jobs defined in `app/infrastructure/scheduler/jobs.py`. Jobs call services or agents directly; they do not use the quarantined event bus.

### Frontend routes

| Path | Page |
|---|---|
| `/` | Dashboard |
| `/assistant` | Chat |
| `/assistant/history` | Conversation list |
| `/assistant/history/:id` | Conversation detail |
| `/actions` | Pending HITL actions |
| `/tickets` | Freshservice ticket list |
| `/tickets/:id` | Ticket detail + ClickUp workflow |
| `/settings` | App settings |

### Prompts

Versioned prompt files live in `app/prompts/` and `app/agents/*/prompts/`. Filenames use a `_v1.txt` suffix. Load them by reading the file at the module level — don't inline prompts in Python code.
