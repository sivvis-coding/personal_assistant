"""Document domain value objects."""

from app.domain.shared.base_value_object import ValueObject


class DocType(ValueObject):
    """Allowed document types."""

    TICKET = "ticket"
    TASK = "task"
    CONVERSATION = "conversation"
    COMMIT = "commit"
    PULL_REQUEST = "pull_request"
    DECISION = "decision"


class DocSource(ValueObject):
    """Allowed document sources."""

    FRESHSERVICE = "freshservice"
    CLICKUP = "clickup"
    SLACK = "slack"
    TEAMS = "teams"
    GITHUB = "github"
    OUTLOOK = "outlook"
    CALENDAR = "calendar"
    MANUAL = "manual"
