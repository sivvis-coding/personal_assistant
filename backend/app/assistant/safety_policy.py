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
            Completed or rejected actions cannot be replayed. Failed actions CAN be
            retried — the executors only mark an action failed before its primary
            external write succeeds, so retrying does not normally duplicate it.
            Known exception: if a save_time_entry ClickUp task was created but the
            time entry registration failed, retrying creates a second ClickUp task.
        """
        if action.status not in ("proposed", "failed"):
            raise ValueError("Only proposed or failed actions can be approved or executed.")
        if action.requires_approval is not True:
            raise ValueError("Assistant actions must require approval.")
        if action.action_type == "prepare_clickup_us":
            self._ensure_prepare_clickup_us_payload(action.payload)
        if action.action_type == "save_time_entry":
            self._ensure_save_time_entry_payload(action.payload)
        if action.action_type == "reply_freshservice_ticket":
            self._ensure_reply_freshservice_ticket_payload(action.ticket_id, action.payload)
        if action.action_type == "resolve_freshservice_ticket":
            if not action.ticket_id:
                raise ValueError("resolve_freshservice_ticket requires a ticket_id.")
        if action.action_type == "request_info_freshservice_ticket":
            self._ensure_request_info_payload(action.ticket_id, action.payload)
        if action.action_type == "send_ticket_to_backlog":
            if not action.ticket_id:
                raise ValueError("send_ticket_to_backlog requires a ticket_id.")

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

    def _ensure_request_info_payload(self, ticket_id: str | None, payload: dict) -> None:
        if not ticket_id:
            raise ValueError("request_info_freshservice_ticket requires a ticket_id.")
        body = payload.get("body")
        if not body or not str(body).strip():
            raise ValueError("request_info_freshservice_ticket payload requires a non-empty 'body'.")

    def _ensure_prepare_clickup_us_payload(self, payload: dict) -> None:
        """Validate the payload for a prepare_clickup_us action.

        Parameters:
            payload: Action-specific payload.

        Returns:
            None when the payload is valid.

        Edge cases:
            The user story is generated at propose time and stored in
            'user_story'; a 'description' is the fallback source used to
            (re)generate it at execution. At least one must be present, or the
            generated task would be meaningless.
        """
        description = payload.get("description")
        user_story = payload.get("user_story")
        has_description = bool(description and str(description).strip())
        has_user_story = isinstance(user_story, dict) and bool(user_story)
        if not has_description and not has_user_story:
            raise ValueError("prepare_clickup_us payload requires a 'description' or a 'user_story'.")

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
