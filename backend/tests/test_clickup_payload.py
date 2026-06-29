from app.core.config import Settings
from app.integrations.clickup import ClickUpClient
from app.integrations.clickup_contract import (
    CLICKUP_CUSTOM_FIELD_ACCEPTANCE_CRITERIA_ID,
    CLICKUP_CUSTOM_FIELD_CONSTRAINTS_ID,
    CLICKUP_CUSTOM_FIELD_FUNCTIONAL_DESCRIPTION_ID,
    CLICKUP_CUSTOM_FIELD_OUT_OF_SCOPE_ID,
    CLICKUP_CUSTOM_FIELD_REQUESTED_BY_ID,
    CLICKUP_CUSTOM_FIELD_USER_STORY_STATEMENT_ID,
    CLICKUP_USER_STORY_CUSTOM_ITEM_ID,
)
from app.schemas.ai import UserStory


def test_should_build_clickup_payload_with_user_story_custom_fields() -> None:
    """Verify ClickUp payload matches configured user story custom fields.

    Parameters:
        None.

    Returns:
        None.

    Edge cases:
        Custom field IDs are workspace-specific constants, not environment settings.
    """
    # Arrange
    client = ClickUpClient(Settings())
    story = UserStory(
        title="Create task from ticket",
        description="Detailed task description.",
        acceptance_criteria_in_gerkin="Given context\nWhen approved\nThen create task",
        constraints="No duplicate tasks",
        user_story_statement="As a user, I want a task, so that work is tracked.",
        out_of_scope="Sending ticket replies",
        requested_by="Mock Customer",
        functional_description="Create a ClickUp task from reviewed story data.",
    )

    # Act
    payload = client._build_user_story_task_payload(story)

    # Assert
    assert payload["name"] == story.title
    assert payload["description"] == story.description
    assert payload["custom_item_id"] == CLICKUP_USER_STORY_CUSTOM_ITEM_ID
    assert {field["id"] for field in payload["custom_fields"]} == {
        CLICKUP_CUSTOM_FIELD_CONSTRAINTS_ID,
        CLICKUP_CUSTOM_FIELD_USER_STORY_STATEMENT_ID,
        CLICKUP_CUSTOM_FIELD_OUT_OF_SCOPE_ID,
        CLICKUP_CUSTOM_FIELD_ACCEPTANCE_CRITERIA_ID,
        CLICKUP_CUSTOM_FIELD_REQUESTED_BY_ID,
        CLICKUP_CUSTOM_FIELD_FUNCTIONAL_DESCRIPTION_ID,
    }
