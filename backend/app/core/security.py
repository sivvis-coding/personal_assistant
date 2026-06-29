from fastapi import Header, HTTPException, status

from app.core.config import Settings


def require_local_app_key(settings: Settings, provided_key: str | None) -> None:
    """Validate local API key when authentication is enabled.

    Parameters:
        settings: Application settings containing the configured local key.
        provided_key: Header value sent by the client.

    Returns:
        None when access is allowed.

    Edge cases:
        Empty configured key disables authentication for local development.
    """
    expected_key = settings.local_app_api_key.strip()
    if not expected_key:
        return
    if provided_key != expected_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid local app key")


async def get_local_app_key_header(x_local_app_key: str | None = Header(default=None)) -> str | None:
    """Extract the `X-Local-App-Key` header from a request.

    Parameters:
        x_local_app_key: Header value provided by FastAPI.

    Returns:
        Header value or None.

    Edge cases:
        Missing header returns None so the security function can decide policy.
    """
    return x_local_app_key
