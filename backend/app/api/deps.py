import logging

from fastapi import Depends, Request

from app.agents.conversation.agent import ConversationAgent
from app.agents.time.agent import TimeAgent
from app.assistant.action_executor import AssistantActionExecutor
from app.assistant.context_builder import AssistantContextBuilder
from app.assistant.conversation_service import AssistantConversationService
from app.assistant.safety_policy import AssistantSafetyPolicy
from app.core.config import Settings, get_settings
from app.core.llm.provider import LLMProvider
from app.core.memory.interface import MemoryFacade
from app.core.security import get_local_app_key_header, require_local_app_key
from app.db.mongo import MongoManager
from app.integrations.clickup import ClickUpClient
from app.integrations.fresh import FreshClient
from app.integrations.openai_client import OpenAIClient
from app.repositories.ai_draft_repository import AiDraftRepository
from app.repositories.app_settings_repository import AppSettingsRepository
from app.repositories.assistant_action_repository import AssistantActionRepository
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.integration_link_repository import IntegrationLinkRepository
from app.repositories.ticket_cache_repository import TicketCacheRepository
from app.repositories.workflow_run_repository import WorkflowRunRepository
from app.services.ai_service import AiService
from app.services.clickup_service import ClickUpService
from app.services.clickup_status_sync_service import ClickUpStatusSyncService
from app.services.ticket_service import TicketService
from app.tools.assistant_action.tool import AssistantActionTool
from app.tools.base import ToolRegistry
from app.tools.clickup_time.tool import ClickUpTimeTool
from app.tools.freshservice.adapter import FreshserviceAdapter
from app.tools.ticket_to_clickup.tool import TicketToClickUpTool

logger = logging.getLogger(__name__)

# DI strategy: deps.py is the single wiring source for all FastAPI dependencies.
# The dependency-injector container (core/di/container.py) owns the event-driven
# architecture (EventBus, Orchestrator, agents, scheduler) and bootstraps the three
# cross-cutting singletons (memory_facade, llm_provider, tool_registry).  main.py
# copies those three objects into app.state during lifespan so that deps.py can
# read them without coupling to the container's Python API.


async def require_auth(
    settings: Settings = Depends(get_settings),
    provided_key: str | None = Depends(get_local_app_key_header),
) -> None:
    """FastAPI dependency that enforces local header authentication.

    Parameters:
        settings: Application settings.
        provided_key: Value of X-Local-App-Key header.

    Returns:
        None when request is authorized.

    Edge cases:
        Empty LOCAL_APP_API_KEY disables authentication.
    """
    require_local_app_key(settings, provided_key)


def get_mongo_manager(request: Request) -> MongoManager:
    """Return Mongo manager stored in FastAPI application state.

    Parameters:
        request: FastAPI request.

    Returns:
        Mongo manager.

    Edge cases:
        Missing state means app lifespan was not initialized.
    """
    return request.app.state.mongo_manager


def get_ticket_service(
    mongo_manager: MongoManager = Depends(get_mongo_manager), settings: Settings = Depends(get_settings)
) -> TicketService:
    """Create ticket service dependency.

    A new TicketService is constructed per request so that settings overrides
    applied by test fixtures (or hot-config-reload) are always picked up.
    TicketService itself is stateless beyond its constructor arguments, so
    per-request construction is safe and inexpensive.

    Parameters:
        mongo_manager: Mongo manager dependency.
        settings: Application settings.

    Returns:
        Ticket service.
    """
    return TicketService(FreshClient(settings), TicketCacheRepository(mongo_manager.database))


def get_ai_service(settings: Settings = Depends(get_settings)) -> AiService:
    """Create AI service dependency.

    Parameters:
        settings: Application settings.

    Returns:
        AI service.

    Edge cases:
        Missing OpenAI key creates mock-capable client.
    """
    return AiService(OpenAIClient(settings))


def get_clickup_client(settings: Settings = Depends(get_settings)) -> ClickUpClient:
    """Create ClickUp client dependency.

    Parameters:
        settings: Application settings.

    Returns:
        ClickUp client.

    Edge cases:
        Missing credentials create mock-capable client.
    """
    return ClickUpClient(settings)


def get_clickup_service(clickup_client: ClickUpClient = Depends(get_clickup_client)) -> ClickUpService:
    """Create ClickUp service dependency.

    Parameters:
        clickup_client: ClickUp client dependency.

    Returns:
        ClickUp service.

    Edge cases:
        None.
    """
    return ClickUpService(clickup_client)


def get_ai_draft_repository(mongo_manager: MongoManager = Depends(get_mongo_manager)) -> AiDraftRepository:
    """Create AI draft repository dependency.

    Parameters:
        mongo_manager: Mongo manager dependency.

    Returns:
        AI draft repository.

    Edge cases:
        None.
    """
    return AiDraftRepository(mongo_manager.database)


def get_workflow_run_repository(mongo_manager: MongoManager = Depends(get_mongo_manager)) -> WorkflowRunRepository:
    """Create workflow run repository dependency.

    Parameters:
        mongo_manager: Mongo manager dependency.

    Returns:
        Workflow run repository.

    Edge cases:
        None.
    """
    return WorkflowRunRepository(mongo_manager.database)


def get_integration_link_repository(mongo_manager: MongoManager = Depends(get_mongo_manager)) -> IntegrationLinkRepository:
    """Create integration link repository dependency.

    Parameters:
        mongo_manager: Mongo manager dependency.

    Returns:
        Integration link repository.

    Edge cases:
        None.
    """
    return IntegrationLinkRepository(mongo_manager.database)


def get_conversation_repository(mongo_manager: MongoManager = Depends(get_mongo_manager)) -> ConversationRepository:
    """Create assistant conversation repository dependency.

    Parameters:
        mongo_manager: Mongo manager dependency.

    Returns:
        Conversation repository.

    Edge cases:
        None.
    """
    return ConversationRepository(mongo_manager.database)


def get_assistant_action_repository(mongo_manager: MongoManager = Depends(get_mongo_manager)) -> AssistantActionRepository:
    """Create assistant action repository dependency.

    Parameters:
        mongo_manager: Mongo manager dependency.

    Returns:
        Assistant action repository.

    Edge cases:
        None.
    """
    return AssistantActionRepository(mongo_manager.database)


def get_app_settings_repository(mongo_manager: MongoManager = Depends(get_mongo_manager)) -> AppSettingsRepository:
    """Create app settings repository dependency.

    Parameters:
        mongo_manager: Mongo manager dependency.

    Returns:
        App settings repository.

    Edge cases:
        None.
    """
    return AppSettingsRepository(mongo_manager.database)


def get_assistant_context_builder(
    ticket_service: TicketService = Depends(get_ticket_service),
    clickup_service: ClickUpService = Depends(get_clickup_service),
    integration_link_repository: IntegrationLinkRepository = Depends(get_integration_link_repository),
) -> AssistantContextBuilder:
    """Create assistant context builder dependency.

    Parameters:
        ticket_service: Ticket service dependency.
        clickup_service: ClickUp service dependency.
        integration_link_repository: Integration link repository dependency.

    Returns:
        Assistant context builder.

    Edge cases:
        None.
    """
    return AssistantContextBuilder(ticket_service, clickup_service, integration_link_repository)


def get_memory_facade(request: Request) -> MemoryFacade:
    """Return the memory facade stored in application state.

    The facade is constructed during lifespan startup and stored in
    app.state.memory_facade so this factory does not couple to the
    dependency-injector container API.

    Parameters:
        request: FastAPI request.

    Returns:
        Memory facade instance.

    Edge cases:
        Raises AttributeError if lifespan did not complete successfully.
    """
    return request.app.state.memory_facade


def get_time_agent(
    memory_facade: MemoryFacade = Depends(get_memory_facade),
) -> TimeAgent:
    """Create time agent dependency.

    Parameters:
        memory_facade: Memory facade from the DI container.

    Returns:
        Time agent instance with ClickUp time tool for client resolution.

    Edge cases:
        The agent is stateless and safe to create per request.
    """
    return TimeAgent(
        memory_facade=memory_facade,
        clickup_time_tool=ClickUpTimeTool(),
    )


def get_clickup_time_tool() -> ClickUpTimeTool:
    """Create ClickUp time tool dependency.

    Returns:
        ClickUp time tool instance.

    Edge cases:
        The tool is stateless and safe to create per request.
    """
    return ClickUpTimeTool()


def get_ticket_to_clickup_tool(
    ticket_service: TicketService = Depends(get_ticket_service),
    ai_service: AiService = Depends(get_ai_service),
    ai_draft_repository: AiDraftRepository = Depends(get_ai_draft_repository),
    integration_link_repository: IntegrationLinkRepository = Depends(get_integration_link_repository),
    workflow_run_repository: WorkflowRunRepository = Depends(get_workflow_run_repository),
    clickup_client: ClickUpClient = Depends(get_clickup_client),
) -> TicketToClickUpTool:
    """Create ticket-to-ClickUp tool dependency.

    Parameters:
        ticket_service: Ticket service dependency.
        ai_service: AI service dependency.
        ai_draft_repository: AI draft repository dependency.
        integration_link_repository: Integration link repository dependency.
        workflow_run_repository: Workflow run repository dependency.
        clickup_client: ClickUp client dependency.

    Returns:
        Ticket-to-ClickUp tool instance.

    Edge cases:
        The tool is stateless and safe to create per request.
    """
    return TicketToClickUpTool(
        ticket_service=ticket_service,
        ai_service=ai_service,
        ai_draft_repository=ai_draft_repository,
        integration_link_repository=integration_link_repository,
        workflow_run_repository=workflow_run_repository,
        clickup_client=clickup_client,
    )


def get_assistant_action_tool(
    action_repository: AssistantActionRepository = Depends(get_assistant_action_repository),
) -> AssistantActionTool:
    """Create assistant action tool dependency.

    Parameters:
        action_repository: Assistant action repository dependency.

    Returns:
        Assistant action tool backed by the repository.

    Edge cases:
        The tool is stateless and safe to create per request.
    """
    return AssistantActionTool(action_repository)


def get_llm_provider(request: Request) -> LLMProvider:
    """Return the LLM provider stored in application state.

    The provider is constructed during lifespan startup and stored in
    app.state.llm_provider so this factory does not couple to the
    dependency-injector container API.

    Parameters:
        request: FastAPI request.

    Returns:
        LLM provider instance.

    Edge cases:
        Raises AttributeError if lifespan did not complete successfully.
    """
    return request.app.state.llm_provider


def get_tool_registry(request: Request) -> ToolRegistry:
    """Return the tool registry stored in application state.

    The registry is populated during lifespan bootstrap and stored in
    app.state.tool_registry so this factory does not couple to the
    dependency-injector container API.

    Parameters:
        request: FastAPI request.

    Returns:
        Tool registry instance (already populated with all registered tools).

    Edge cases:
        Raises AttributeError if lifespan did not complete successfully.
    """
    return request.app.state.tool_registry


def get_conversation_agent(
    llm_provider: LLMProvider = Depends(get_llm_provider),
) -> ConversationAgent:
    """Create conversation agent dependency.

    Parameters:
        llm_provider: LLM provider dependency.

    Returns:
        Conversation agent instance.

    Edge cases:
        The agent is stateless and safe to create per request.
    """
    return ConversationAgent(llm_provider)


def get_assistant_conversation_service(
    conversation_repository: ConversationRepository = Depends(get_conversation_repository),
    assistant_action_tool: AssistantActionTool = Depends(get_assistant_action_tool),
    context_builder: AssistantContextBuilder = Depends(get_assistant_context_builder),
    conversation_agent: ConversationAgent = Depends(get_conversation_agent),
    time_agent: TimeAgent = Depends(get_time_agent),
    tool_registry: ToolRegistry = Depends(get_tool_registry),
) -> AssistantConversationService:
    """Create assistant conversation service dependency.

    Parameters:
        conversation_repository: Conversation repository dependency.
        assistant_action_tool: Tool for creating pending assistant actions.
        context_builder: Assistant context builder dependency.
        conversation_agent: LLM-backed conversation agent dependency.
        time_agent: Time agent dependency.
        tool_registry: Tool registry dependency.

    Returns:
        Assistant conversation service.

    Edge cases:
        None.
    """
    return AssistantConversationService(
        conversation_repository,
        assistant_action_tool,
        context_builder,
        conversation_agent,
        time_agent,
        tool_registry,
    )


def get_freshservice_adapter(
    ticket_service: TicketService = Depends(get_ticket_service),
    settings: Settings = Depends(get_settings),
) -> FreshserviceAdapter:
    """Create Freshservice adapter dependency.

    Parameters:
        ticket_service: Ticket service dependency.
        settings: Application settings dependency.

    Returns:
        Freshservice adapter instance.

    Edge cases:
        The adapter is stateless and safe to create per request.
    """
    return FreshserviceAdapter(ticket_service, FreshClient(settings))


def get_clickup_status_sync_service(
    integration_link_repository: IntegrationLinkRepository = Depends(get_integration_link_repository),
    clickup_client: ClickUpClient = Depends(get_clickup_client),
    freshservice_adapter: FreshserviceAdapter = Depends(get_freshservice_adapter),
) -> ClickUpStatusSyncService:
    """Create ClickUp status sync service dependency.

    Parameters:
        integration_link_repository: Integration link repository dependency.
        clickup_client: ClickUp client dependency.
        freshservice_adapter: Freshservice adapter dependency.

    Returns:
        ClickUp status sync service.

    Edge cases:
        The service is stateless and safe to create per request.
    """
    return ClickUpStatusSyncService(integration_link_repository, clickup_client, freshservice_adapter)


def get_assistant_action_executor(
    action_repository: AssistantActionRepository = Depends(get_assistant_action_repository),
    ticket_to_clickup_tool: TicketToClickUpTool = Depends(get_ticket_to_clickup_tool),
    clickup_time_tool: ClickUpTimeTool = Depends(get_clickup_time_tool),
    freshservice_adapter: FreshserviceAdapter = Depends(get_freshservice_adapter),
) -> AssistantActionExecutor:
    """Create assistant action executor dependency.

    Parameters:
        action_repository: Assistant action repository dependency.
        ticket_to_clickup_tool: Ticket-to-ClickUp tool dependency.
        clickup_time_tool: ClickUp time tool dependency.
        freshservice_adapter: Freshservice adapter dependency.

    Returns:
        Assistant action executor.

    Edge cases:
        Safety policy is created with no hidden external dependencies.
    """
    return AssistantActionExecutor(
        action_repository,
        AssistantSafetyPolicy(),
        ticket_to_clickup_tool,
        clickup_time_tool,
        freshservice_adapter,
    )
