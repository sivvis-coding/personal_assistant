from app.assistant.schemas.actions import AssistantAction
from app.assistant.schemas.time_agent import TimeEntryActionPayload


class AssistantSafetyPolicy:
    """Validate assistant actions before execution.

    Parameters:
        None.

    Returns:
        Policy object used by action execution.

    Edge cases:
        Conservative failures are preferred over accidental external writes.
    """

    def ensure_can_execute(self, action: AssistantAction) -> None:
        """Validate that an action can be executed safely.

        Parameters:
            action: Assistant action requested for execution.

        Returns:
            None when the action is safe to execute.

        Edge cases:
            Proposed status is required so completed or rejected actions cannot be replayed.
        """
        if action.status != "proposed":
            raise ValueError("Only proposed actions can be approved or executed.")
        if action.requires_approval is not True:
            raise ValueError("Assistant actions must require approval.")
        if action.action_type in ("prepare_clickup_task", "approve_clickup_task") and not action.ticket_id:
            raise ValueError("Ticket actions require a ticket_id.")
        if action.action_type == "save_time_entry":
            self._ensure_save_time_entry_payload(action.payload)
        if action.action_type == "reply_freshservice_ticket":
            self._ensure_reply_freshservice_ticket_payload(action.ticket_id, action.payload)

    def _ensure_reply_freshservice_ticket_payload(self, ticket_id: str | None, payload: dict) -> None:
        """Validate the payload for a reply_freshservice_ticket action.

        Parameters:
            ticket_id: Related Fresh ticket ID from the action record.
            payload: Action-specific payload.

        Returns:
            None when the payload is valid.

        Edge cases:
            Both ticket_id and a non-empty body are required so no blank
            replies reach customers.
        """
        if not ticket_id:
            raise ValueError("reply_freshservice_ticket requires a ticket_id.")
        body = payload.get("body")
        if not body or not str(body).strip():
            raise ValueError("reply_freshservice_ticket payload requires a non-empty 'body'.")

    def _ensure_save_time_entry_payload(self, payload: dict) -> None:
        """Validate the payload for a save_time_entry action.

        Parameters:
            payload: Action-specific payload.

        Returns:
            None when the payload is valid.

        Edge cases:
            Raises ValueError when required fields are missing or malformed.
        """
        try:
            TimeEntryActionPayload.model_validate(payload)
        except Exception as error:
            raise ValueError(f"Invalid save_time_entry payload: {error}") from error
