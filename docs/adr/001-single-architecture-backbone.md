# ADR-001: Single Architecture Backbone

- **Status:** Accepted
- **Date:** 2026-06-30

## Context

The backend runs two competing execution stacks side by side.

**Pila A — Direct-call backbone (what production actually serves).**
Every HTTP endpoint flows through it:

```
FastAPI routes
  -> app/api/deps.py        (manual `Depends` factories + a module-global TicketService)
  -> AssistantConversationService
  -> ConversationAgent.respond()
  -> AssistantActionExecutor (HITL approve/reject gate)
  -> tools -> repositories -> Mongo
```

It is a plain FastAPI-`Depends` graph with no event bus. The HITL executor runs approved actions through `TicketToClickUpTool.execute(operation="prepare"/"approve")` and `clickup_time_tool`.

**Pila B — Event-driven stack (scheduler-only, broken).**
Wired by `app/core/di/container.py` (dependency-injector):

```
Scheduler -> Orchestrator -> EventRouter -> BaseAgent.handle()
  -> agents emit events -> EventBus.publish()
```

Two compounding defects make it non-functional beyond a single hop:

1. **The EventBus has no subscribers.** The only call to `EventBus.subscribe()` lives inside `EventRegistry.apply()`, and `apply()` is never called anywhere. Agents are dispatched by the `EventRouter`, but events agents *produce* are handed to `InProcessEventBus.publish()` — which, with zero subscribers, silently drops them. Every chained reaction dies after the first agent (e.g. `FreshserviceAgent` emits `TicketWithoutTaskDetected` -> `ClickUpAgent` never runs).
2. **Only the scheduler reaches Pila B at all.** `Orchestrator.handle()` / `start_workflow()` is never called from any API route; `app.state.orchestrator` is set but never read. The scheduler's cron jobs are the sole live entry point. Two scheduled jobs (`TasksReviewRequested`, `TimesheetReviewRequested`) have no matching `router.register(...)`, so they resolve to zero agents and no-op.

Pila B carries two DI systems, an event bus, a router, a context manager, a domain-event taxonomy, and per-agent memory config — yet delivers *less* working behavior than Pila A. This matters now because every planned feature (Steps 3-7) would otherwise have to choose a stack or straddle both. We need one backbone first.

## Decision

**Pila A is the single backbone.** All request and scheduled flows converge on the direct-call path. Rationale: this is a single-user personal assistant, not a multi-tenant scaled product; Pila B's indirection buys fan-out flexibility we do not need and pay for in complexity and silent failure.

The good parts of Pila B are kept and rewired to call services/tools **directly** instead of publishing to a dead bus.

## What stays from Pila B

- **`ToolInterface` / `ToolRegistry`** (`backend/app/tools/base.py`) — the uniform tool contract and registry are the right abstraction. Keep them as the single tool layer for both paths.
- **`BaseAgent` contract** (`backend/app/agents/base.py`) — the agent shape (id, handle, result) is fine. Agents stay; they call services/tools directly and return results rather than emitting domain events onto the bus.
- **The scheduler** (`backend/app/infrastructure/scheduler/`) — cron jobs are still wanted. Rewire jobs to invoke services/agents directly instead of going through `Orchestrator` + `EventBus`.

## What gets removed (or quarantined)

If clean deletion is acceptable now, delete; otherwise move to `backend/app/_graveyard/` so it stops loading and stops being imported by `container.py`:

- `EventBus` / `InProcessEventBus` (`backend/app/core/events/`, `backend/app/infrastructure/events/`)
- `EventRegistry` (`backend/app/core/events/registry.py`)
- `Orchestrator` (`backend/app/orchestrator/orchestrator.py`)
- `EventRouter` (`backend/app/orchestrator/router.py`)
- `ContextManager` (`backend/app/orchestrator/context_manager.py`) unless a direct caller still needs tool lookup
- The domain-event taxonomy under `backend/app/domain/*/events.py` insofar as it exists only to feed the bus

Either way, `container.py` must no longer construct or depend on `EventBus`, `Orchestrator`, or `EventRouter`, and `app.state.orchestrator` must be removed.

## What gets fixed (regardless of the above)

These are correctness/safety bugs, not cleanup:

1. **ClickUpAgent must route through `TicketToClickUpTool`.**
   `backend/app/agents/clickup/agent.py` calls `context.get_tool("clickup")` with `operation="create_task"` (the raw `ClickUpTool`), creating tasks with **no AI user-story generation, no draft persistence, no `WorkflowRunRepository` audit, and no HITL approval step** — directly violating the README rule that ClickUp creation requires review+approval. It must instead use `TicketToClickUpTool` (`backend/app/tools/ticket_to_clickup/tool.py`), which implements the audited, idempotent two-phase prepare/approve flow.

2. **`TicketToClickUpTool` must be registered in DI.**
   `bootstrap()` in `container.py` registers `FreshserviceTool`, `ClickUpTool`, `MongoTool`, `ClickUpTimeTool`, `AssistantActionTool` — but **not** `TicketToClickUpTool`. It is reachable only via the manual factory `get_ticket_to_clickup_tool` (deps.py), so no event-path agent can resolve it. Register it.

3. **Single shared `relation_type` constant.**
   A `RelationType` value object already exists (`backend/app/domain/integration_link/value_objects.py`) with `TICKET_TO_TASK = "ticket_to_task"`, and `MongoTool` already uses `RelationType.TICKET_TO_TASK`. But `TicketToClickUpTool` ignores the enum and hardcodes the literal `"created_clickup_task"` — a value not even present in `RelationType`. The same logical ticket->ClickUp link is therefore persisted under two different values, so a link written by one path is invisible to the other's `find_link` lookup and cross-path dedup silently fails. Pick **one** canonical value on `RelationType` and import it everywhere a ticket->task link is read or written; remove the inline `"created_clickup_task"` literal.

## Consequences

**Unblocks:**
- Steps 3-7 can target a single, known-good path instead of choosing or bridging stacks.
- ClickUp task creation regains its audit trail, idempotency, and HITL approval gate on every path.
- Cross-path duplicate detection works once `relation_type` is unified.
- One DI/wiring story to reason about, test, and onboard against.

**Given up (accepted cost):**
- Event-driven fan-out (one event -> many independent subscribers) is gone for now. If a future feature genuinely needs decoupled fan-out, it is reintroduced deliberately with subscriber wiring proven by a test — not resurrected from quarantined code.
- Quarantined-not-deleted code (if we choose `_graveyard/`) is dead weight until a follow-up removes it.

## Checklist for this ADR to be "done"

- [ ] `container.py` no longer constructs or imports `EventBus`/`InProcessEventBus`, `EventRegistry`, `Orchestrator`, or `EventRouter`; `app.state.orchestrator` is removed.
- [ ] `core/events/` and `infrastructure/events/` are deleted or moved to `_graveyard/` and no longer imported by live code.
- [ ] `ToolInterface`/`ToolRegistry`, `BaseAgent`, and the scheduler remain and are reachable from the direct-call path.
- [ ] Scheduler jobs invoke services/agents directly (no `Orchestrator`/`EventBus` in the call path); no scheduled job resolves to zero handlers.
- [ ] `ClickUpAgent` creates tasks exclusively via `TicketToClickUpTool`; no remaining call to the raw `ClickUpTool` `create_task` operation for ticket-sourced tasks.
- [ ] `TicketToClickUpTool` is registered in the tool registry in `bootstrap()`.
- [ ] All ticket->task links use a single `RelationType` value imported from `backend/app/domain/integration_link/value_objects.py`; no inline `"ticket_to_task"` or `"created_clickup_task"` literals remain.
- [ ] A test asserts ClickUp creation via the agent path is idempotent (second run finds the existing `IntegrationLink` and creates no duplicate).
- [ ] A test asserts no ClickUp task is created without passing through the prepare/approve HITL gate.
- [ ] `pytest` passes and the app boots with the event stack removed/quarantined.
