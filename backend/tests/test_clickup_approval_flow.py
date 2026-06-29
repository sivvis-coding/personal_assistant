from pathlib import Path

WORKFLOW_SOURCE = Path(__file__).resolve().parents[1] / "app" / "workflows" / "ticket_to_clickup_task.py"


def test_should_not_accept_clickup_client_in_prepare_workflow() -> None:
    """Verify review preparation cannot create ClickUp tasks by dependency design.

    Parameters:
        None.

    Returns:
        None.

    Edge cases:
        This protects the approval boundary from accidental regression.
    """
    # Arrange / Act
    source = WORKFLOW_SOURCE.read_text(encoding="utf-8")
    prepare_signature = source.split("async def prepare_clickup_task_from_ticket_workflow", maxsplit=1)[1].split(") ->", maxsplit=1)[0]

    # Assert
    assert "clickup_client" not in prepare_signature


def test_should_require_clickup_client_only_in_approval_workflow() -> None:
    """Verify only approval workflow can create ClickUp tasks.

    Parameters:
        None.

    Returns:
        None.

    Edge cases:
        Approval workflow still checks duplicate integration links before creating tasks.
    """
    # Arrange / Act
    source = WORKFLOW_SOURCE.read_text(encoding="utf-8")
    approval_signature = source.split("async def approve_clickup_task_from_ticket_workflow", maxsplit=1)[1].split(") ->", maxsplit=1)[0]

    # Assert
    assert "clickup_client" in approval_signature
    assert "approved_user_story" in approval_signature
