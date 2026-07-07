"""Tests for the personal-list client options endpoint logic."""

import pytest

from app.api.clickup import get_personal_list_clients
from app.schemas.settings import AppSettings
from app.tools.base import ToolResult


class FakeSettingsService:
    """Settings service stub returning a fixed personal ClickUp list id."""

    def __init__(self, list_id: str = "list-1") -> None:
        self._list_id = list_id

    async def get_settings(self) -> AppSettings:
        return AppSettings(clickup_personal_list_id=self._list_id)


class FakeClickUpTimeTool:
    """ClickUp time tool stub returning deterministic client options."""

    def __init__(self, clients: list[str] | None = None, fail: bool = False) -> None:
        self._clients = clients or []
        self._fail = fail

    async def execute(self, **kwargs) -> ToolResult:
        if self._fail:
            return ToolResult.error(message="boom")
        assert kwargs["operation"] == "get_clients"
        assert kwargs["list_id"] == "list-1"
        return ToolResult.ok(data={"clients": self._clients})


@pytest.mark.asyncio
async def test_should_return_configured_client_options() -> None:
    """Verify the endpoint returns the client options resolved via the tool.

    Parameters:
        None.

    Returns:
        None.
    """
    response = await get_personal_list_clients(
        settings_service=FakeSettingsService(),
        clickup_time_tool=FakeClickUpTimeTool(clients=["003-Caixa Bank", "3900-PI - IT & Innovación"]),
    )

    assert response.clients == ["003-Caixa Bank", "3900-PI - IT & Innovación"]


@pytest.mark.asyncio
async def test_should_return_empty_list_when_no_personal_list_configured() -> None:
    """Verify an empty response when the personal list is not configured, no tool call made."""
    response = await get_personal_list_clients(
        settings_service=FakeSettingsService(list_id=""),
        clickup_time_tool=FakeClickUpTimeTool(clients=["should not be reached"]),
    )

    assert response.clients == []


@pytest.mark.asyncio
async def test_should_return_empty_list_when_tool_call_fails() -> None:
    """Verify a failed tool call degrades to an empty list instead of raising."""
    response = await get_personal_list_clients(
        settings_service=FakeSettingsService(),
        clickup_time_tool=FakeClickUpTimeTool(fail=True),
    )

    assert response.clients == []
