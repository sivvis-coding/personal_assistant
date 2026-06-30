"""Integration link value objects."""

from dataclasses import dataclass

from app.domain.shared.base_value_object import ValueObject


@dataclass(frozen=True)
class RelationType(ValueObject):
    """Allowed relation types between systems."""

    TICKET_TO_TASK = "ticket_to_task"
    TASK_TO_TICKET = "task_to_ticket"
    TICKET_TO_DOCUMENT = "ticket_to_document"
    TASK_TO_DOCUMENT = "task_to_document"
