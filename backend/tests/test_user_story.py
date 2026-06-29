from app.schemas.ai import UserStory


def test_should_render_user_story_in_required_markdown_format() -> None:
    """Verify user story Markdown follows ClickUp-oriented sections.

    Parameters:
        None.

    Returns:
        None.

    Edge cases:
        ClickUp custom field content should remain visible in readable Markdown.
    """
    # Arrange
    story = UserStory(
        title="Create task from ticket",
        description="Ticket with high impact.",
        acceptance_criteria_in_gerkin="Given a ticket\nWhen it is approved\nThen a ClickUp task is created",
        constraints="Store Fresh ↔ ClickUp relation",
        user_story_statement="As a support user, I want to create a task from a ticket, so that work can be tracked.",
        out_of_scope="Automatic customer replies",
        requested_by="Support team",
        functional_description="The app creates a ClickUp task after approval.",
    )

    # Act
    markdown = story.to_markdown()

    # Assert
    assert "User Story Statement:" in markdown
    assert "Acceptance Criteria:" in markdown
    assert "Technical Notes / Constraints:" in markdown
    assert "Out of Scope:" in markdown
    assert "Automatic customer replies" in markdown
