"""Dependency injection container."""

from dependency_injector import containers, providers

from app.agents.clickup.agent import ClickUpAgent
from app.agents.clickup_status_sync.agent import ClickUpStatusSyncAgent
from app.agents.freshservice.agent import FreshserviceAgent
from app.agents.notification.agent import NotificationAgent
from app.agents.planner.agent import PlannerAgent
from app.agents.prioritization.agent import PrioritizationAgent
from app.agents.time.agent import TimeAgent
from app.agents.triage.agent import TicketTriageAgent
from app.core.config import Settings
from app.core.constants import DEFAULT_USER_ID
from app.core.llm.provider import LLMProvider
from app.core.memory.interface import MemoryFacade
from app.db.mongo import MongoManager
from app.infrastructure.llm.openai_provider import OpenAILLMProvider
from app.infrastructure.memory.facade import DefaultMemoryFacade
from app.infrastructure.scheduler.scheduler import Scheduler
from app.integrations.clickup import ClickUpClient
from app.integrations.fresh import FreshClient
from app.integrations.openai_client import OpenAIClient
from app.repositories.ai_draft_repository import AiDraftRepository
from app.repositories.assistant_action_repository import AssistantActionRepository
from app.repositories.integration_link_repository import IntegrationLinkRepository
from app.repositories.ticket_cache_repository import TicketCacheRepository
from app.repositories.workflow_run_repository import WorkflowRunRepository
from app.services.ai_service import AiService
from app.services.clickup_status_sync_service import ClickUpStatusSyncService
from app.services.ticket_service import TicketService
from app.tools.assistant_action.tool import AssistantActionTool
from app.tools.base import ToolRegistry
from app.tools.clickup.tool import ClickUpTool
from app.tools.clickup_time.tool import ClickUpTimeTool
from app.tools.freshservice.adapter import FreshserviceAdapter
from app.tools.freshservice.tool import FreshserviceTool
from app.tools.mongo.tool import MongoTool
from app.tools.ticket_to_clickup.tool import TicketToClickUpTool


class Container(containers.DeclarativeContainer):
    """Application dependency injection container."""

    settings = providers.Singleton(Settings)

    mongo_manager = providers.Singleton(MongoManager, settings=settings)

    fresh_client = providers.Singleton(FreshClient, settings=settings)
    clickup_client = providers.Singleton(ClickUpClient, settings=settings)

    ticket_cache_repository = providers.Singleton(
        TicketCacheRepository,
        database=mongo_manager.provided.database,
    )
    ticket_service = providers.Singleton(
        TicketService,
        fresh_client=fresh_client,
        ticket_cache_repository=ticket_cache_repository,
    )

    integration_link_repository = providers.Singleton(
        IntegrationLinkRepository,
        database=mongo_manager.provided.database,
    )
    assistant_action_repository = providers.Singleton(
        AssistantActionRepository,
        database=mongo_manager.provided.database,
    )
    ai_draft_repository = providers.Singleton(
        AiDraftRepository,
        database=mongo_manager.provided.database,
    )
    workflow_run_repository = providers.Singleton(
        WorkflowRunRepository,
        database=mongo_manager.provided.database,
    )

    openai_client = providers.Singleton(OpenAIClient, settings=settings)
    ai_service = providers.Singleton(AiService, openai_client=openai_client)

    ticket_to_clickup_tool = providers.Singleton(
        TicketToClickUpTool,
        ticket_service=ticket_service,
        ai_service=ai_service,
        ai_draft_repository=ai_draft_repository,
        integration_link_repository=integration_link_repository,
        workflow_run_repository=workflow_run_repository,
        clickup_client=clickup_client,
    )

    tool_registry = providers.Singleton(ToolRegistry)

    memory_facade: providers.Singleton[MemoryFacade] = providers.Singleton(
        DefaultMemoryFacade,
        database=mongo_manager.provided.database,
        user_id=DEFAULT_USER_ID,
    )

    llm_provider: providers.Singleton[LLMProvider] = providers.Singleton(
        OpenAILLMProvider,
        settings=settings,
    )

    freshservice_agent = providers.Singleton(
        FreshserviceAgent,
        memory_facade=memory_facade,
    )
    clickup_agent = providers.Singleton(
        ClickUpAgent,
        memory_facade=memory_facade,
    )
    planner_agent = providers.Singleton(
        PlannerAgent,
        memory_facade=memory_facade,
        llm_provider=llm_provider,
    )
    notification_agent = providers.Singleton(
        NotificationAgent,
        memory_facade=memory_facade,
    )
    ticket_triage_agent = providers.Singleton(
        TicketTriageAgent,
        memory_facade=memory_facade,
    )
    prioritization_agent = providers.Singleton(
        PrioritizationAgent,
        memory_facade=memory_facade,
    )
    time_agent = providers.Singleton(
        TimeAgent,
        memory_facade=memory_facade,
        clickup_time_tool=providers.Singleton(ClickUpTimeTool),
    )

    freshservice_adapter = providers.Singleton(
        FreshserviceAdapter,
        ticket_service=ticket_service,
        client=fresh_client,
    )

    clickup_status_sync_service = providers.Singleton(
        ClickUpStatusSyncService,
        integration_link_repository=integration_link_repository,
        clickup_client=clickup_client,
        freshservice_adapter=freshservice_adapter,
    )

    clickup_status_sync_agent = providers.Singleton(
        ClickUpStatusSyncAgent,
        memory_facade=memory_facade,
        sync_service=clickup_status_sync_service,
    )

    scheduler = providers.Singleton(Scheduler)


async def bootstrap(container: Container) -> None:
    """Bootstrap the direct-call architecture and start the scheduler.

    Parameters:
        container: Configured DI container.

    Returns:
        None — the Orchestrator layer has been removed.

    Edge cases:
        Tool registration and scheduler wiring happen here so the container
        itself stays declarative.
    """
    manager = container.mongo_manager()
    await manager.connect()

    await IntegrationLinkRepository(manager.database).ensure_indexes()
    await AssistantActionRepository(manager.database).ensure_indexes()

    registry = container.tool_registry()
    registry.register(FreshserviceTool(container.ticket_service(), container.fresh_client()))
    registry.register(ClickUpTool(container.clickup_client()))
    registry.register(MongoTool(container.integration_link_repository()))
    registry.register(ClickUpTimeTool())
    registry.register(AssistantActionTool(container.assistant_action_repository()))
    registry.register(container.ticket_to_clickup_tool())

    scheduler = container.scheduler()
    configure_scheduler(scheduler, container)
    scheduler.start()


from app.infrastructure.scheduler.jobs import configure_scheduler  # noqa: E402
