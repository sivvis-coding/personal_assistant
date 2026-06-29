import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.core.security import require_local_app_key


def test_should_allow_request_when_local_app_key_is_empty() -> None:
    """Verify disabled local auth allows requests without a header.

    Parameters:
        None.

    Returns:
        None.

    Edge cases:
        Empty configured key is the intentional local development mode.
    """
    # Arrange
    settings = Settings(local_app_api_key="")

    # Act
    result = require_local_app_key(settings, None)

    # Assert
    assert result is None


def test_should_allow_request_when_local_app_key_matches() -> None:
    """Verify matching local auth header allows the request.

    Parameters:
        None.

    Returns:
        None.

    Edge cases:
        Exact match is required; trimming is only applied to configured value.
    """
    # Arrange
    settings = Settings(local_app_api_key="secret")

    # Act
    result = require_local_app_key(settings, "secret")

    # Assert
    assert result is None


def test_should_return_error_when_local_app_key_does_not_match() -> None:
    """Verify invalid local auth header is rejected.

    Parameters:
        None.

    Returns:
        None.

    Edge cases:
        Missing header behaves like an invalid key when auth is enabled.
    """
    # Arrange
    settings = Settings(local_app_api_key="secret")

    # Act / Assert
    with pytest.raises(HTTPException) as error:
        require_local_app_key(settings, "wrong")
    assert error.value.status_code == 401
