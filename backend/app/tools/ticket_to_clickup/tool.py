"""Ticket-to-ClickUp tool implementation."""

from typing import Any

from app.domain.integration_link.value_objects import RelationType
from app.integrations.clickup import ClickUpClient
from app.repositories.ai_draft_repository import AiDraftRepository
from app.repositories.integration_link_repository import IntegrationLinkRepository
from app.repositories.workflow_run_repository import WorkflowRunRepository
from app.schemas.ai import AiDraftDocument, UserStory
from app.schemas.clickup import (
    ClickUpTaskResult,
    CreateClickUpTaskWorkflowResponse,
    PrepareClickUpTaskWorkflowResponse,
)
from app.schemas.integration import IntegrationLinkDocument
from app.services.ai_service import AiService
from app.services.ticket_service import TicketService
from app.tools.base import ToolInterface, ToolParameter, ToolResult


class TicketToClickUpTool(ToolInterface):
    """Tool exposing ticket-to-ClickUp workflow operations to agents.

    This tool encapsulates preparing a ClickUp task proposal from a ticket
    and creating it after explicit approval. It keeps the prepare step free
    of ClickUp write dependencies by design.

    Parameters:
        ticket_service: Service used to retrieve ticket data.
        ai_service: Service used to generate user stories.
        ai_draft_repository: Repository used to persist generated drafts.
        integration_link_repository: Repository used to persist Fresh-to-ClickUp links.
        workflow_run_repository: Repository used to audit workflow execution.
        clickup_client: Client used to create ClickUp tasks. Optional because
            the prepare operation does not need it.

    Returns:
        Ticket-to-ClickUp tool instance.
    """

    name = "ticket_to_clickup"
    description = "Prepare and approve ClickUp tasks from Freshservice tickets."
    parameters = [
        ToolParameter(name="operation", type="string", description="One of: prepare, approve"),
        ToolParameter(name="ticket_id", type="string", description="Freshservice ticket identifier"),
        ToolParameter(name="user_story", type="object", description="Reviewed user story for approve", required=False),
    ]

    def __init__(
        self,
        ticket_service: TicketService,
        ai_service: AiService,
        ai_draft_repository: AiDraftRepository,
        integration_link_repository: IntegrationLinkRepository,
        workflow_run_repository: WorkflowRunRepository,
        clickup_client: ClickUpClient | None = None,
    ) -> None:
        """Initialize the tool with its dependencies.

        Parameters:
            ticket_service: Service used to retrieve ticket data.
            ai_service: Service used to generate user stories.
            ai_draft_repository: Repository used to persist generated drafts.
            integration_link_repository: Repository used to persist integration links.
            workflow_run_repository: Repository used to audit workflow execution.
            clickup_client: Optional ClickUp client. Required only for approve.

        Returns:
            None.

        Edge cases:
            The ClickUp client is intentionally optional to keep prepare safe.
        """
        self._ticket_service = ticket_service
        self._ai_service = ai_service
        self._ai_draft_repository = ai_draft_repository
        self._integration_link_repository = integration_link_repository
        self._workflow_run_repository = workflow_run_repository
        self._clickup_client = clickup_client

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute a ticket-to-ClickUp operation.

        Parameters:
            **kwargs: Operation-specific parameters.

        Returns:
            Tool execution result.

        Edge cases:
            Unknown operations return an error result without raising.
        """
        operation = kwargs.get("operation")

        try:
            if operation == "prepare":
                ticket_id = self._require(kwargs, "ticket_id")
                response = await self._prepare(ticket_id)
                return ToolResult.ok(data=response.model_dump(mode="json"), message="ClickUp task proposal ready")

            if operation == "approve":
                ticket_id = self._require(kwargs, "ticket_id")
                user_story_data = self._require(kwargs, "user_story")
                user_story = UserStory.model_validate(user_story_data)
                list_id = kwargs.get("list_id") or None
                response = await self._approve(ticket_id, user_story, list_id=list_id)
                return ToolResult.ok(data=response.model_dump(mode="json"), message="ClickUp task created")

            return ToolResult.error(message=f"Unknown operation '{operation}' for ticket_to_clickup tool")
        except Exception as exc:  # noqa: BLE001
            return ToolResult.error(message=str(exc))

    async def _prepare(self, ticket_id: str) -> PrepareClickUpTaskWorkflowResponse:
        """Prepare a ClickUp task proposal without creating a real task.

        Parameters:
            ticket_id: Fresh ticket identifier.

        Returns:
            ClickUp task preparation response.

        Edge cases:
            This method never calls ClickUp, even when credentials are configured.
        """
        run_id = await self._workflow_run_repository.start("prepare_clickup_task", ticket_id, {"ticket_id": ticket_id})
        try:
            ticket_response = await self._ticket_service.get_ticket(ticket_id)
            user_story = await self._ai_service.ticket_to_user_story(ticket_response.ticket)
            draft_id = await self._ai_draft_repository.save_draft(
                AiDraftDocument(
                    fresh_ticket_id=ticket_id,
                    type="user_story",
                    content=user_story.to_markdown(),
                    structured_content=user_story.model_dump(),
                    model=self._ai_service.model_name,
                    prompt_version="ticket_user_story_v1",
                )
            )

            response = PrepareClickUpTaskWorkflowResponse(
                ticket_id=ticket_id,
                user_story=user_story,
                draft_id=draft_id,
                workflow_run_id=run_id,
                requires_approval=True,
            )
            await self._workflow_run_repository.finish_success(run_id, response.model_dump())
            return response
        except Exception as error:
            await self._workflow_run_repository.finish_failure(run_id, str(error))
            raise

    async def _approve(
        self, ticket_id: str, approved_user_story: UserStory, list_id: str | None = None
    ) -> CreateClickUpTaskWorkflowResponse:
        """Create a ClickUp task after explicit user approval.

        Parameters:
            ticket_id: Fresh ticket identifier.
            approved_user_story: Reviewed user story from the frontend.
            list_id: Optional ClickUp list ID override. Falls back to settings default.

        Returns:
            ClickUp task creation response.

        Edge cases:
            Existing integration link prevents duplicate ClickUp task creation.
        """
        if self._clickup_client is None:
            raise ValueError("ClickUp client is required for approve operation")

        run_id = await self._workflow_run_repository.start(
            "approve_clickup_task",
            ticket_id,
            {"ticket_id": ticket_id, "approved_user_story": approved_user_story.model_dump()},
        )
        try:
            ticket_response = await self._ticket_service.get_ticket(ticket_id)

            existing_link = await self._integration_link_repository.find_link(
                "fresh", ticket_id, RelationType.TICKET_TO_TASK
            )
            if existing_link:
                clickup_task = ClickUpTaskResult(
                    id=str(existing_link["target_id"]),
                    url=existing_link.get("target_url"),
                    source="cache",
                )
                link_id = str(existing_link["id"])
            else:
                clickup_task = await self._clickup_client.create_task_from_ticket(
                    ticket_response.ticket, approved_user_story, list_id=list_id
                )
                link_id = await self._integration_link_repository.save_link(
                    IntegrationLinkDocument(
                        source_system="fresh",
                        source_id=ticket_id,
                        target_system="clickup",
                        target_id=clickup_task.id,
                        target_url=clickup_task.url,
                        relation_type=RelationType.TICKET_TO_TASK,
                    )
                )

            response = CreateClickUpTaskWorkflowResponse(
                ticket_id=ticket_id,
                user_story=approved_user_story,
                clickup_task=clickup_task,
                integration_link_id=link_id,
                workflow_run_id=run_id,
            )
            await self._workflow_run_repository.finish_success(run_id, response.model_dump())
            return response
        except Exception as error:
            await self._workflow_run_repository.finish_failure(run_id, str(error))
            raise

    @staticmethod
    def _require(kwargs: dict[str, Any], key: str) -> Any:
        """Return a required parameter or raise a clear error."""
        if key not in kwargs or kwargs[key] is None:
            raise ValueError(f"Missing required parameter '{key}'")
        return kwargs[key]
