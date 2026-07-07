from app.schemas.settings import AppSettings


def test_should_extract_list_id_from_clickup_view_id() -> None:
    """Verify a pasted ClickUp view id (type-listId-sequence) is normalized.

    ClickUp's "Copy link" on the Home > Personal List feature yields a
    composite view id rather than the plain numeric list id the REST API
    expects, which otherwise causes a 400 Bad Request when creating tasks.
    """
    settings = AppSettings(clickup_personal_list_id="6-901505357877-1")

    assert settings.clickup_personal_list_id == "901505357877"


def test_should_extract_list_id_from_full_clickup_url() -> None:
    """Verify a pasted full ClickUp URL ending in a composite view id is normalized."""
    settings = AppSettings(
        clickup_personal_list_id="https://app.clickup.com/9013391444/v/l/6-901505357877-1"
    )

    assert settings.clickup_personal_list_id == "901505357877"


def test_should_leave_plain_list_id_unchanged() -> None:
    """Verify an already-correct plain numeric list id is not altered."""
    settings = AppSettings(clickup_personal_list_id="901505357877")

    assert settings.clickup_personal_list_id == "901505357877"


def test_should_leave_unrecognized_format_unchanged() -> None:
    """Verify unrecognized formats are passed through rather than mangled."""
    settings = AppSettings(clickup_personal_list_id="some-custom-id")

    assert settings.clickup_personal_list_id == "some-custom-id"


def test_should_leave_empty_list_id_unchanged() -> None:
    """Verify an unconfigured (empty) personal list id stays empty."""
    settings = AppSettings(clickup_personal_list_id="")

    assert settings.clickup_personal_list_id == ""
