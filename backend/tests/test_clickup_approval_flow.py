from pathlib import Path

from app.tools.ticket_to_clickup.tool import TicketToClickUpTool

TOOL_SOURCE = Path(__file__).resolve().parents[1] / "app" / "tools" / "ticket_to_clickup" / "tool.py"


def test_should_not_use_clickup_client_in_prepare_operation() -> None:
    """Verify review preparation cannot create ClickUp tasks by dependency design.

    Parameters:
        None.

    Returns:
        None.

    Edge cases:
        This protects the approval boundary from accidental regression.
    """
    source = TOOL_SOURCE.read_text(encoding="utf-8")
    prepare_method = source.split("async def _prepare", maxsplit=1)[1].split("async def _approve", maxsplit=1)[0]

    assert "clickup_client" not in prepare_method
    assert "_clickup_client" not in prepare_method


def test_should_require_clickup_client_in_approve_operation() -> None:
    """Verify only approval operation can create ClickUp tasks.

    Parameters:
        None.

    Returns:
        None.

    Edge cases:
        Approval operation still checks duplicate integration links before creating tasks.
    """
    source = TOOL_SOURCE.read_text(encoding="utf-8")
    approve_method = source.split("async def _approve", maxsplit=1)[1].split("async def _require", maxsplit=1)[0]

    assert "_clickup_client" in approve_method
    assert "create_task_from_ticket" in approve_method


def test_should_expose_prepare_and_approve_operations() -> None:
    """Verify the tool exposes the expected operations and parameters."""
    assert TicketToClickUpTool.name == "ticket_to_clickup"
    assert any(parameter.name == "operation" for parameter in TicketToClickUpTool.parameters)
    assert any(parameter.name == "ticket_id" for parameter in TicketToClickUpTool.parameters)
    assert any(parameter.name == "user_story" for parameter in TicketToClickUpTool.parameters)
