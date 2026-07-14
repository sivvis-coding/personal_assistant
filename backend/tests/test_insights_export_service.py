import json

from app.core.time import utc_now
from app.schemas.insights import (
    AutomationOpportunity,
    Bottleneck,
    CategoryMetric,
    DepartmentKnowledge,
    KnowledgeResponse,
    KnowledgeTheme,
    RecurringIssue,
    TicketRef,
)
from app.services.insights_export_service import InsightsExportService


class FakeKnowledgeService:
    def __init__(self, response: KnowledgeResponse) -> None:
        self._response = response
        self.calls = 0

    async def get_persisted(self):
        self.calls += 1
        return self._response


class FakeArchiveRepo:
    def __init__(self, docs: list[dict]) -> None:
        self.docs = docs
        self.stream_calls = 0

    async def stream_all(self, workspace_id=None):
        self.stream_calls += 1
        for d in self.docs:
            if workspace_id and d["workspace_id"] != workspace_id:
                continue
            yield d


def _knowledge_response() -> KnowledgeResponse:
    dept = DepartmentKnowledge(
        workspace_id="w1",
        name="IT",
        total_tickets=10,
        themes=[
            KnowledgeTheme(
                title="Accesos y permisos",
                summary="Resumen del tema",
                symptoms="sintomas",
                root_causes="causas",
                resolution_steps="pasos",
                frequency=5,
                workspaces=["w1"],
                ticket_refs=[TicketRef(workspace_id="w1", ticket_id="101", subject="No puedo entrar")],
            )
        ],
        recurring=[RecurringIssue(label="Accesos y permisos", count=5, ticket_refs=[])],
        bottlenecks=[
            Bottleneck(
                title="Aprobaciones lentas",
                description="Las aprobaciones tardan demasiado",
                severity="high",
                category="Accesos y permisos",
                ticket_refs=[TicketRef(workspace_id="w1", ticket_id="101", subject="No puedo entrar")],
            )
        ],
        automation=[
            AutomationOpportunity(
                title="Auto-reset de contraseña",
                description="Permitir autoservicio",
                rationale="Ahorra tiempo de agentes",
                category="Accesos y permisos",
            )
        ],
        metrics=[CategoryMetric(category="Accesos y permisos", volume=5, avg_resolution_hours=3.2, reopen_rate=0.1)],
    )
    return KnowledgeResponse(departments=[dept], model="test-model", generated_at=utc_now(), persisted=True)


def _ticket_doc(workspace_id="w1", ticket_id="101", with_signature=True) -> dict:
    return {
        "workspace_id": workspace_id,
        "workspace_name": "IT",
        "ticket_id": ticket_id,
        "subject": "No puedo entrar",
        "status": "resolved",
        "priority": "high",
        "requester": {"name": "Juan Pérez"},
        "description": "No puedo acceder al sistema",
        "conversations": [
            {"kind": "customer_reply", "body_text": "Sigo sin poder entrar"},
            {"kind": "agent_reply", "body_text": "Te reseteamos la contraseña"},
            {"kind": "private_note", "body_text": "Revisar logs de AD"},
        ],
        "created_at_fresh": utc_now(),
        "updated_at_fresh": utc_now(),
        "signature": (
            {
                "problem": "No puede iniciar sesión",
                "category": "Accesos y permisos",
                "root_cause": "contraseña caducada",
                "resolution": "reseteo de contraseña",
                "product_area": "AD",
            }
            if with_signature
            else None
        ),
    }


async def _collect(agen) -> list[dict]:
    return [json.loads(line.decode("utf-8")) async for line in agen]


async def test_stream_themes_only_is_the_default_scope():
    knowledge = FakeKnowledgeService(_knowledge_response())
    archive = FakeArchiveRepo([_ticket_doc()])
    service = InsightsExportService(knowledge, archive)

    records = await _collect(service.stream(InsightsExportService.DEFAULT_INCLUDE))

    assert archive.stream_calls == 0
    assert {r["source_type"] for r in records} == {"theme"}
    assert len(records) == 1


async def test_stream_all_knowledge_source_types_covers_everything_and_skips_recurring():
    knowledge = FakeKnowledgeService(_knowledge_response())
    archive = FakeArchiveRepo([_ticket_doc()])
    service = InsightsExportService(knowledge, archive)

    records = await _collect(service.stream({"themes", "bottlenecks", "automation", "metrics"}))

    assert archive.stream_calls == 0
    source_types = {r["source_type"] for r in records}
    assert source_types == {"theme", "bottleneck", "automation", "metric"}
    assert len(records) == 4


async def test_stream_tickets_only_does_not_touch_knowledge_service():
    knowledge = FakeKnowledgeService(_knowledge_response())
    archive = FakeArchiveRepo([_ticket_doc()])
    service = InsightsExportService(knowledge, archive)

    records = await _collect(service.stream({"tickets"}))

    assert knowledge.calls == 0
    assert len(records) == 1
    assert records[0]["source_type"] == "ticket"
    assert records[0]["id"] == "ticket:w1:101"


async def test_ticket_record_includes_signature_and_labeled_conversation():
    knowledge = FakeKnowledgeService(_knowledge_response())
    archive = FakeArchiveRepo([_ticket_doc()])
    service = InsightsExportService(knowledge, archive)

    [record] = await _collect(service.stream({"tickets"}))

    content = record["content"]
    assert "Diagnóstico (IA)" in content
    assert "contraseña caducada" in content
    assert "[Cliente] Sigo sin poder entrar" in content
    assert "[Agente] Te reseteamos la contraseña" in content
    assert "[Nota privada] Revisar logs de AD" in content
    assert record["category"] == "Accesos y permisos"


async def test_theme_record_metadata():
    knowledge = FakeKnowledgeService(_knowledge_response())
    archive = FakeArchiveRepo([])
    service = InsightsExportService(knowledge, archive)

    records = await _collect(service.stream({"themes"}))
    theme = next(r for r in records if r["source_type"] == "theme")

    assert theme["id"] == "theme:w1:accesos-y-permisos"
    assert theme["ticket_ids"] == ["101"]
    assert theme["frequency"] == 5
    assert theme["department"] == "IT"


async def test_workspace_id_filters_both_knowledge_and_tickets():
    knowledge = FakeKnowledgeService(_knowledge_response())
    archive = FakeArchiveRepo([_ticket_doc(workspace_id="w1"), _ticket_doc(workspace_id="w2", ticket_id="202")])
    service = InsightsExportService(knowledge, archive)

    records = await _collect(service.stream({"themes", "tickets"}, workspace_id="w2"))

    assert len(records) == 1
    assert records[0]["source_type"] == "ticket"
    assert records[0]["workspace_id"] == "w2"


async def test_ticket_without_signature_omits_diagnosis_block():
    knowledge = FakeKnowledgeService(_knowledge_response())
    archive = FakeArchiveRepo([_ticket_doc(with_signature=False)])
    service = InsightsExportService(knowledge, archive)

    [record] = await _collect(service.stream({"tickets"}))

    assert "Diagnóstico (IA)" not in record["content"]
    assert "category" not in record
