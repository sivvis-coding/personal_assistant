from app.assistant.safety_policy import AssistantSafetyPolicy
from app.assistant.schemas.actions import AssistantAction, AssistantActionCreate
from app.repositories.assistant_action_repository import AssistantActionRepository
from app.tools.base import ToolResult
from app.tools.clickup_time.tool import ClickUpTimeTool
from app.tools.freshservice.adapter import FreshserviceAdapter
from app.tools.freshservice.schemas import ReplyTicketInput, RequestInfoTicketInput, ResolveTicketInput
from app.tools.ticket_to_clickup.tool import TicketToClickUpTool


class AssistantActionExecutor:
    """Execute approved assistant actions using safe tools.

    Parameters:
        action_repository: Repository storing assistant actions.
        safety_policy: Policy used before any execution.
        ticket_to_clickup_tool: Tool for preparing and approving ClickUp tasks.
        clickup_time_tool: Tool for creating ClickUp time entries.
        freshservice_adapter: Adapter for Freshservice write operations.

    Returns:
        Executor for assistant actions.

    Edge cases:
        ClickUp creation is split into prepare and approve actions to preserve review safety.
        Public Freshservice replies require an approved reply_freshservice_ticket action.
    """

    def __init__(
        self,
        action_repository: AssistantActionRepository,
        safety_policy: AssistantSafetyPolicy,
        ticket_to_clickup_tool: TicketToClickUpTool,
        clickup_time_tool: ClickUpTimeTool,
        freshservice_adapter: FreshserviceAdapter,
    ) -> None:
        """Initialize the assistant action executor.

        Parameters:
            action_repository: Repository for action state.
            safety_policy: Policy validator for execution boundaries.
            ticket_to_clickup_tool: Tool for ticket-to-ClickUp workflows.
            clickup_time_tool: Tool for creating ClickUp time entries.
            freshservice_adapter: Adapter for Freshservice write operations.

        Returns:
            None.

        Edge cases:
            All write-capable capabilities come through tools for safety review.
        """
        self._action_repository = action_repository
        self._safety_policy = safety_policy
        self._ticket_to_clickup_tool = ticket_to_clickup_tool
        self._clickup_time_tool = clickup_time_tool
        self._freshservice_adapter = freshservice_adapter

    async def approve(self, action_id: str) -> AssistantAction:
        """Approve and execute one assistant action.

        Parameters:
            action_id: Assistant action ID.

        Returns:
            Updated action with execution result.

        Edge cases:
            Prepare actions create a second approval action instead of creating ClickUp immediately.
        """
        action = await self._action_repository.get_action(action_id)
        if action is None:
            raise ValueError("Assistant action not found.")
        self._safety_policy.ensure_can_execute(action)
        if action.action_type == "prepare_clickup_task":
            return await self._prepare_clickup_task(action)
        if action.action_type == "approve_clickup_task":
            return await self._approve_clickup_task(action)
        if action.action_type == "save_time_entry":
            return await self._save_time_entry(action)
        if action.action_type == "reply_freshservice_ticket":
            return await self._reply_freshservice_ticket(action)
        if action.action_type == "resolve_freshservice_ticket":
            return await self._resolve_freshservice_ticket(action)
        if action.action_type == "request_info_freshservice_ticket":
            return await self._request_info_freshservice_ticket(action)
        if action.action_type == "send_ticket_to_backlog":
            return await self._send_ticket_to_backlog(action)
        raise ValueError(f"Unsupported assistant action type: {action.action_type}")

    async def reject(self, action_id: str) -> AssistantAction:
        """Reject one proposed assistant action.

        Parameters:
            action_id: Assistant action ID.

        Returns:
            Updated rejected action.

        Edge cases:
            Missing actions fail explicitly instead of silently succeeding.
        """
        action = await self._action_repository.get_action(action_id)
        if action is None:
            raise ValueError("Assistant action not found.")
        return await self._action_repository.update_status(action_id, "rejected")

    async def _prepare_clickup_task(self, action: AssistantAction) -> AssistantAction:
        """Prepare a ClickUp task and propose the final create action.

        Parameters:
            action: Approved prepare action.

        Returns:
            Completed prepare action with review result.

        Edge cases:
            The final ClickUp task is not created here.
        """
        assert action.ticket_id is not None
        tool_result: ToolResult = await self._ticket_to_clickup_tool.execute(
            operation="prepare", ticket_id=action.ticket_id
        )
        if not tool_result.success:
            return await self._action_repository.update_status(
                action.id, "failed", result={"message": tool_result.message, "error": True}
            )
        prepared = tool_result.data
        follow_up = await self._action_repository.create_action(
            AssistantActionCreate(
                action_type="approve_clickup_task",
                title=f"Crear tarea ClickUp para ticket {action.ticket_id}",
                description="Revisa la user story generada antes de crear la tarea externa.",
                ticket_id=action.ticket_id,
                payload={"user_story": prepared["user_story"]},
            )
        )
        result = {"prepared": prepared, "next_action_id": follow_up.id}
        return await self._action_repository.update_status(action.id, "completed", result=result)

    async def _approve_clickup_task(self, action: AssistantAction) -> AssistantAction:
        """Create the ClickUp task after explicit second approval.

        Parameters:
            action: Approved final creation action.

        Returns:
            Completed action with ClickUp creation result.

        Edge cases:
            User story payload must come from the prepare step.
        """
        assert action.ticket_id is not None
        user_story = action.payload.get("user_story")
        tool_result: ToolResult = await self._ticket_to_clickup_tool.execute(
            operation="approve",
            ticket_id=action.ticket_id,
            user_story=user_story,
        )
        if not tool_result.success:
            return await self._action_repository.update_status(
                action.id, "failed", result={"message": tool_result.message, "error": True}
            )
        return await self._action_repository.update_status(action.id, "completed", result=tool_result.data)

    async def _save_time_entry(self, action: AssistantAction) -> AssistantAction:
        """Create a ClickUp task and register a time entry after approval.

        Parameters:
            action: Approved save_time_entry action with a valid payload.

        Returns:
            Completed action with the ClickUp tool result.

        Edge cases:
            Tool failures are stored as failed action results.
        """
        payload = action.payload
        tool_result: ToolResult = await self._clickup_time_tool.execute(
            operation="save",
            task_name=payload["task_name"],
            description=payload["description"],
            start_datetime=payload["start_datetime"],
            end_datetime=payload["end_datetime"],
            client_name=payload.get("client_name", ""),
            approved=True,
        )
        if not tool_result.success:
            return await self._action_repository.update_status(
                action.id, "failed", result={"message": tool_result.message, "error": True}
            )
        message = tool_result.data.get("message") if isinstance(tool_result.data, dict) else str(tool_result.data)
        return await self._action_repository.update_status(action.id, "completed", result={"message": message})

    async def _send_ticket_to_backlog(self, action: AssistantAction) -> AssistantAction:
        """Generate user story, create ClickUp task, and reply to the ticket with the task link.

        Parameters:
            action: Approved send_ticket_to_backlog action. Optional 'body' in payload
                    is used as the reply prefix; the ClickUp URL is always appended.

        Returns:
            Completed action with the ClickUp task URL and reply result.

        Edge cases:
            If a ClickUp task already exists for the ticket the existing link is reused.
            The reply is only sent when the ClickUp task step succeeds.
        """
        assert action.ticket_id is not None

        # Step 1: generate user story
        prepare_result: ToolResult = await self._ticket_to_clickup_tool.execute(
            operation="prepare", ticket_id=action.ticket_id
        )
        if not prepare_result.success:
            return await self._action_repository.update_status(
                action.id, "failed", result={"message": prepare_result.message, "error": True}
            )

        user_story = prepare_result.data["user_story"]

        # Step 2: create ClickUp task
        list_id = action.payload.get("list_id") or None
        approve_result: ToolResult = await self._ticket_to_clickup_tool.execute(
            operation="approve", ticket_id=action.ticket_id, user_story=user_story, list_id=list_id
        )
        if not approve_result.success:
            return await self._action_repository.update_status(
                action.id, "failed", result={"message": approve_result.message, "error": True}
            )

        clickup_task = approve_result.data.get("clickup_task", {})
        task_url = clickup_task.get("url") or ""

        # Step 3: reply to ticket with the task link
        body_prefix = str(action.payload.get("body", "")).strip()
        if task_url:
            reply_body = f"{body_prefix}\n\nTarea en ClickUp: {task_url}" if body_prefix else f"Tarea en ClickUp: {task_url}"
        else:
            reply_body = body_prefix or "La tarea ha sido creada en el backlog de ClickUp."

        try:
            reply_result = await self._freshservice_adapter.reply_ticket(
                ReplyTicketInput(ticket_id=action.ticket_id, body=reply_body)
            )
        except Exception as exc:  # noqa: BLE001
            return await self._action_repository.update_status(
                action.id, "failed", result={"message": f"ClickUp task created but reply failed: {exc}", "error": True}
            )

        return await self._action_repository.update_status(
            action.id,
            "completed",
            result={"clickup_task": clickup_task, "reply": reply_result},
        )

    async def _resolve_freshservice_ticket(self, action: AssistantAction) -> AssistantAction:
        """Resolve or close a Freshservice ticket after explicit approval.

        Parameters:
            action: Approved resolve_freshservice_ticket action.

        Returns:
            Completed action with the Fresh API response.

        Edge cases:
            Safety policy enforces ticket_id presence before this is called.
        """
        assert action.ticket_id is not None
        status = str(action.payload.get("status", "resolved"))
        try:
            response = await self._freshservice_adapter.resolve_ticket(
                ResolveTicketInput(ticket_id=action.ticket_id, status=status)  # type: ignore[arg-type]
            )
        except Exception as exc:  # noqa: BLE001
            return await self._action_repository.update_status(
                action.id, "failed", result={"message": str(exc), "error": True}
            )
        return await self._action_repository.update_status(
            action.id, "completed", result={"response": response}
        )

    async def _request_info_freshservice_ticket(self, action: AssistantAction) -> AssistantAction:
        """Reply asking for more information and set ticket to waiting-on-third-party.

        Parameters:
            action: Approved request_info_freshservice_ticket action with a 'body' payload.

        Returns:
            Completed action. The ticket status becomes 7 (waiting on third party).
        """
        assert action.ticket_id is not None
        body = str(action.payload["body"])
        try:
            response = await self._freshservice_adapter.request_info_ticket(
                RequestInfoTicketInput(ticket_id=action.ticket_id, body=body)
            )
        except Exception as exc:  # noqa: BLE001
            return await self._action_repository.update_status(
                action.id, "failed", result={"message": str(exc), "error": True}
            )
        return await self._action_repository.update_status(
            action.id, "completed", result={"response": response}
        )

    async def _reply_freshservice_ticket(self, action: AssistantAction) -> AssistantAction:
        """Send an approved public reply to a Freshservice ticket.

        Parameters:
            action: Approved reply_freshservice_ticket action.  The payload must
                contain a non-empty 'body' field validated by AssistantSafetyPolicy.

        Returns:
            Completed action with the Fresh API response.

        Edge cases:
            Safety policy already enforces non-empty body and ticket_id before
            this method is called.  Adapter failures are stored as failed actions.
        """
        assert action.ticket_id is not None
        body = str(action.payload["body"])
        try:
            response = await self._freshservice_adapter.reply_ticket(
                ReplyTicketInput(ticket_id=action.ticket_id, body=body)
            )
        except Exception as exc:  # noqa: BLE001
            return await self._action_repository.update_status(
                action.id, "failed", result={"message": str(exc), "error": True}
            )
        return await self._action_repository.update_status(
            action.id, "completed", result={"response": response}
        )
