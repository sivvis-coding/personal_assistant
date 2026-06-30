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

## Assistant agent flow

The V2 assistant adds a conversational layer on top of the existing safe workflows:

```txt
POST /assistant/conversations
POST /assistant/conversations/{conversation_id}/messages
GET /assistant/actions/pending
POST /assistant/actions/{action_id}/approve
POST /assistant/actions/{action_id}/reject
```

The assistant currently uses deterministic specialist components:

- Ticket triage: classifies tickets as `action_now`, `backlog_candidate`, `needs_more_info`, `ignore_or_monitor`, or `already_in_backlog`.
- Prioritization: groups tickets into today's focus, next actions, backlog candidates, blocked items, and monitor-only items.
- Time tracking: parses natural language time entries and creates pending `save_time_entry` actions for HITL approval.
- Action approval: creates durable action cards before any write workflow runs.

Safety remains explicit:

1. A backlog request creates a `prepare_clickup_task` action only.
2. Approving that action generates a reviewed user story draft and a second `approve_clickup_task` action.
3. Approving the second action creates the ClickUp task through the existing approval workflow.

This keeps the assistant useful without giving it hidden permission to create external state.

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
backend/app/assistant     Conversational assistant orchestration and specialist agents
```

## Time tracking agent

The Time Agent connects the existing LangChain time tracking tools to the conversational assistant:

```txt
backend/app/assistant/agents/time_agent.py
```

How it works:

1. The user sends a natural language request such as "Imputa 2h hoy a las 09:00 al cliente Acme por revisión".
2. `TimeAgent` extracts duration, client, date, start time, and description.
3. A safe preview is generated and a `save_time_entry` action is created with status `proposed`.
4. The user reviews the action in the chat or in the pending actions panel and clicks **Aprobar**.
5. `AssistantActionExecutor` calls `save_time_entry(approved=true)`, which creates the ClickUp task and registers the time entry.

Supported request patterns:

- Durations: `3h`, `2h30m`, `30min`, `1 hora`
- Clients: `cliente Acme`, `al cliente Globex`
- Dates: `hoy`, `ayer`, `mañana`, `2026-06-29`
- Times: `09:00`, `9h`

If any required field is missing, the agent replies with a clarification request instead of creating a pending action.

## Tests

Backend tests are under `backend/tests`.

Run inside backend environment:

```bash
pytest
```

The backend Docker image installs the test extras so tests can be run inside the backend container during local validation.
