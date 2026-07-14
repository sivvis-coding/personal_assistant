"""Serialize Insights (knowledge base + ticket archive) into plain-text JSONL
export records, for ingestion into an external RAG search index.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from app.repositories.fresh_ticket_archive_repository import FreshTicketArchiveRepository
from app.schemas.insights import (
    AutomationOpportunity,
    Bottleneck,
    CategoryMetric,
    DepartmentKnowledge,
    ExportRecord,
    KnowledgeTheme,
    TicketRef,
)
from app.services.knowledge_service import KnowledgeService

# Label conversation entries by kind so the plain-text transcript carries
# provenance (customer vs agent vs internal note) for the ingesting model.
_CONVO_LABELS = {"customer_reply": "Cliente", "agent_reply": "Agente", "private_note": "Nota privada"}


class InsightsExportService:
    """Turn persisted Insights data into one ExportRecord per semantic unit.

    Parameters:
        knowledge_service: Source for the persisted, per-department knowledge base.
        archive_repository: Source for the raw ticket archive.

    Returns:
        Service that streams newline-delimited JSON, one record per theme,
        bottleneck, automation opportunity, category metric, or ticket —
        each independently indexable plain text + metadata.

    Edge cases:
        Recurring issues are intentionally not exported: they are a ranked
        view of the same themes (same titles/ticket_refs), so exporting them
        would duplicate near-identical content in the search index.
    """

    # Themes carry symptoms + root_causes + resolution_steps — the "how the
    # agent should act for this symptom" knowledge a support RAG needs. The
    # other KB source types (process-improvement facing, not user-facing) and
    # raw tickets are opt-in only, not part of the default export.
    DEFAULT_INCLUDE = frozenset({"themes"})
    KNOWLEDGE_SOURCE_TYPES = frozenset({"themes", "bottlenecks", "automation", "metrics"})

    def __init__(
        self, knowledge_service: KnowledgeService, archive_repository: FreshTicketArchiveRepository
    ) -> None:
        self._knowledge_service = knowledge_service
        self._archive_repository = archive_repository

    async def stream(self, include: set[str], workspace_id: str | None = None) -> AsyncIterator[bytes]:
        """Yield newline-delimited JSON export records.

        Parameters:
            include: Subset of {"themes", "bottlenecks", "automation", "metrics", "tickets"}.
            workspace_id: Optional filter to a single department/workspace.

        Edge cases:
            An unknown include value is simply ignored (no error).
        """
        if include & self.KNOWLEDGE_SOURCE_TYPES:
            response = await self._knowledge_service.get_persisted()
            for department in response.departments:
                if workspace_id and department.workspace_id != workspace_id:
                    continue
                for record in _department_records(department, response.generated_at, include):
                    yield _line(record)
        if "tickets" in include:
            async for doc in self._archive_repository.stream_all(workspace_id):
                yield _line(_ticket_record(doc))


# --- serialization helpers ----------------------------------------------------


def _line(record: ExportRecord) -> bytes:
    return record.model_dump_json(exclude_none=True, exclude_defaults=True).encode("utf-8") + b"\n"


def _slug(text: str) -> str:
    """Normalize a title into a URL/id-safe slug (falls back to a placeholder)."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")
    return slug or "sin-titulo"


def _example_tickets_line(refs: list[TicketRef]) -> str | None:
    if not refs:
        return None
    examples = "; ".join(f"{r.ticket_id} ({r.subject})" if r.subject else r.ticket_id for r in refs)
    return f"Tickets de ejemplo: {examples}"


def _department_records(
    department: DepartmentKnowledge, generated_at: datetime | None, include: set[str]
) -> list[ExportRecord]:
    records: list[ExportRecord] = []
    if "themes" in include:
        for theme in department.themes:
            records.append(_theme_record(department, theme, generated_at))
    if "bottlenecks" in include:
        for bottleneck in department.bottlenecks:
            records.append(_bottleneck_record(department, bottleneck, generated_at))
    if "automation" in include:
        for automation in department.automation:
            records.append(_automation_record(department, automation, generated_at))
    if "metrics" in include:
        for metric in department.metrics:
            records.append(_metric_record(department, metric, generated_at))
    return records


def _theme_record(department: DepartmentKnowledge, theme: KnowledgeTheme, generated_at: datetime | None) -> ExportRecord:
    dept_name = department.name or department.workspace_id
    lines = [f"Departamento: {dept_name}", f"Tema: {theme.title}"]
    if theme.summary:
        lines += ["", "Resumen:", theme.summary]
    if theme.symptoms:
        lines += ["", "Síntomas:", theme.symptoms]
    if theme.root_causes:
        lines += ["", "Causas raíz:", theme.root_causes]
    if theme.resolution_steps:
        lines += ["", "Pasos de resolución:", theme.resolution_steps]
    lines += ["", f"Frecuencia: {theme.frequency} tickets"]
    examples = _example_tickets_line(theme.ticket_refs)
    if examples:
        lines += ["", examples]
    return ExportRecord(
        id=f"theme:{department.workspace_id}:{_slug(theme.title)}",
        content="\n".join(lines),
        source_type="theme",
        department=dept_name,
        workspace_id=department.workspace_id,
        title=theme.title,
        ticket_ids=[r.ticket_id for r in theme.ticket_refs],
        frequency=theme.frequency,
        generated_at=generated_at,
    )


def _bottleneck_record(department: DepartmentKnowledge, bottleneck: Bottleneck, generated_at: datetime | None) -> ExportRecord:
    dept_name = department.name or department.workspace_id
    lines = [
        f"Departamento: {dept_name}",
        f"Cuello de botella: {bottleneck.title}",
        f"Descripción: {bottleneck.description}",
        f"Severidad: {bottleneck.severity}",
    ]
    if bottleneck.category:
        lines.append(f"Categoría: {bottleneck.category}")
    examples = _example_tickets_line(bottleneck.ticket_refs)
    if examples:
        lines += ["", examples]
    return ExportRecord(
        id=f"bottleneck:{department.workspace_id}:{_slug(bottleneck.title)}",
        content="\n".join(lines),
        source_type="bottleneck",
        department=dept_name,
        workspace_id=department.workspace_id,
        title=bottleneck.title,
        ticket_ids=[r.ticket_id for r in bottleneck.ticket_refs],
        category=bottleneck.category,
        severity=bottleneck.severity,
        generated_at=generated_at,
    )


def _automation_record(
    department: DepartmentKnowledge, automation: AutomationOpportunity, generated_at: datetime | None
) -> ExportRecord:
    dept_name = department.name or department.workspace_id
    lines = [
        f"Departamento: {dept_name}",
        f"Oportunidad de automatización: {automation.title}",
        f"Descripción: {automation.description}",
    ]
    if automation.rationale:
        lines.append(f"Justificación: {automation.rationale}")
    if automation.category:
        lines.append(f"Categoría: {automation.category}")
    examples = _example_tickets_line(automation.ticket_refs)
    if examples:
        lines += ["", examples]
    return ExportRecord(
        id=f"automation:{department.workspace_id}:{_slug(automation.title)}",
        content="\n".join(lines),
        source_type="automation",
        department=dept_name,
        workspace_id=department.workspace_id,
        title=automation.title,
        ticket_ids=[r.ticket_id for r in automation.ticket_refs],
        category=automation.category,
        generated_at=generated_at,
    )


def _metric_record(department: DepartmentKnowledge, metric: CategoryMetric, generated_at: datetime | None) -> ExportRecord:
    dept_name = department.name or department.workspace_id
    lines = [
        f"Departamento: {dept_name}",
        f"Categoría: {metric.category}",
        f"Volumen: {metric.volume} tickets",
    ]
    if metric.avg_resolution_hours is not None:
        lines.append(f"Tiempo medio de resolución: {metric.avg_resolution_hours} horas")
    if metric.reopen_rate is not None:
        lines.append(f"Tasa de reapertura: {round(metric.reopen_rate * 100, 1)}%")
    return ExportRecord(
        id=f"metric:{department.workspace_id}:{_slug(metric.category)}",
        content="\n".join(lines),
        source_type="metric",
        department=dept_name,
        workspace_id=department.workspace_id,
        title=metric.category,
        category=metric.category,
        generated_at=generated_at,
    )


def _ticket_record(doc: dict[str, Any]) -> ExportRecord:
    workspace_id = doc.get("workspace_id", "")
    ticket_id = doc.get("ticket_id", "")
    dept_name = doc.get("workspace_name") or workspace_id
    lines = [
        f"Departamento: {dept_name}",
        f"Ticket #{ticket_id} — {doc.get('subject', '')}",
        f"Estado: {doc.get('status', '')} | Prioridad: {doc.get('priority', '')}",
    ]
    requester_name = (doc.get("requester") or {}).get("name")
    if requester_name:
        lines.append(f"Solicitante: {requester_name}")

    description = (doc.get("description") or "").strip()
    if description:
        lines += ["", "Descripción original:", description]

    signature = doc.get("signature") or {}
    if signature:
        lines += ["", "Diagnóstico (IA):", f"Problema: {signature.get('problem', '')}"]
        lines.append(f"Categoría: {signature.get('category', '')}")
        lines.append(f"Causa raíz: {signature.get('root_cause', '')}")
        lines.append(f"Resolución: {signature.get('resolution', '')}")
        if signature.get("product_area"):
            lines.append(f"Área de producto: {signature['product_area']}")

    convo_lines = []
    for convo in doc.get("conversations") or []:
        body = (convo.get("body_text") or "").strip()
        if not body:
            continue
        label = _CONVO_LABELS.get(convo.get("kind"), convo.get("kind") or "")
        convo_lines.append(f"[{label}] {body}")
    if convo_lines:
        lines += ["", "Conversación:", *convo_lines]

    return ExportRecord(
        id=f"ticket:{workspace_id}:{ticket_id}",
        content="\n".join(lines),
        source_type="ticket",
        department=dept_name,
        workspace_id=workspace_id,
        title=doc.get("subject", ""),
        ticket_ids=[ticket_id] if ticket_id else [],
        category=signature.get("category", ""),
        status=doc.get("status", ""),
        created_at=doc.get("created_at_fresh"),
        updated_at=doc.get("updated_at_fresh"),
    )
