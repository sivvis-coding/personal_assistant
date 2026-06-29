# Local Personal Assistant

Local web app for support and task workflows across Freshdesk/Freshservice, ClickUp, MongoDB, and OpenAI.

## Architecture

- Backend: Python 3.12, FastAPI, Motor, Pydantic, OpenAI SDK.
- Frontend: React, Vite, TypeScript.
- Database: MongoDB.
- Containers: Docker Compose.
- Local authentication: `X-Local-App-Key` header when `LOCAL_APP_API_KEY` is configured.

## Run locally

```bash
cp .env.example .env
docker compose up --build
```

Open:

- Frontend: http://localhost:5173
- Backend docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

## Safety rules

- The app never sends Fresh replies automatically.
- `FreshClient.add_reply()` exists only for future explicit use.
- ClickUp task creation requires a review step before approval.
- Missing external credentials use mock responses.
- Secrets must stay in `.env`, never in source code.
- MongoDB is local cache/audit storage, not the external source of truth.

## Fresh ticket filtering

The tickets page loads tickets assigned to you by default:

```txt
GET /tickets?scope=mine
```

Configure your Freshservice agent identifier in `.env`:

```env
FRESH_ASSIGNED_AGENT_ID=123456
FRESH_ASSIGNED_AGENT_FIELD=agent_id
```

Use the frontend selector or call `GET /tickets?scope=all` to view every ticket. If `FRESH_ASSIGNED_AGENT_ID` is empty, the backend cannot infer "me" and falls back to the regular tickets endpoint.

## ClickUp approval flow

The app separates AI generation from external task creation:

1. `POST /tickets/{ticket_id}/prepare-clickup-task` generates and stores a reviewed user story draft.
2. The frontend lets you edit the user story.
3. `POST /tickets/{ticket_id}/approve-clickup-task` creates the ClickUp task only after approval.

Approved ClickUp tasks use the configured internal ClickUp contract:

- `custom_item_id`: `1006`
- Technical Notes / Constraints
- User Story Statement
- Out of Scope
- Acceptance Criteria
- Requested By
- Functional Description

Workflow history is available at:

```txt
GET /workflow-runs?limit=50
GET /workflow-runs?fresh_ticket_id=1001
```

## Backend structure

```txt
backend/app/api           FastAPI routes and dependencies
backend/app/core          settings, security, shared helpers
backend/app/db            Mongo connection lifecycle
backend/app/repositories  Mongo collection access
backend/app/integrations  External API clients
backend/app/workflows     Business orchestration
backend/app/schemas       Pydantic contracts
backend/app/prompts       Versioned AI prompts
backend/app/tools         Isolated LangChain tools for future agents
```

## Future agent tools

The backend includes an isolated LangChain tool module for future agent usage:

```txt
backend/app/tools/clickup_time_tracking.py
```

Available tools:

- `get_available_clients`: reads the configured ClickUp list and returns available client names when the client field is a dropdown/labels field.
- `prepare_time_entry`: previews a time entry without creating ClickUp state.
- `save_time_entry`: creates a ClickUp task and registers a time entry using Europe/Madrid local datetimes. Requires `approved=true`.

These tools are not connected to the current frontend or API routes yet. They are intended for a future agent that can impute hours in ClickUp.

## Tests

Backend tests are under `backend/tests`.

Run inside backend environment:

```bash
pytest
```

The backend Docker image installs the test extras so tests can be run inside the backend container during local validation.
