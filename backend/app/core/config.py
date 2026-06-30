from functools import lru_cache
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Parameters:
        Values are provided by environment variables or `.env`.

    Returns:
        Settings instance used across the backend.

    Edge cases:
        Empty credential values intentionally disable external integrations.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongo_url: str = "mongodb://mongo:27017/local_assistant"
    mongo_db_name: str = "local_assistant"
    openai_api_key: str = ""
    fresh_base_url: str = ""
    fresh_api_key: str = ""
    fresh_assigned_agent_id: str = ""
    fresh_assigned_agent_field: str = "agent_id"
    fresh_workspace_id: str = ""
    clickup_api_key: str = ""
    clickup_team_id: str = ""
    clickup_list_id: str = ""
    local_app_api_key: str = ""
    openai_model: str = "gpt-5.4"

    @property
    def has_fresh_credentials(self) -> bool:
        """Return whether Fresh integration credentials are configured.

        Parameters:
            None.

        Returns:
            True when base URL and API key are present.

        Edge cases:
            Whitespace-only values are treated as missing.
        """
        return bool(self.fresh_base_url.strip() and self.fresh_api_key.strip())

    @property
    def has_fresh_assigned_agent_id(self) -> bool:
        """Return whether assigned-ticket filtering can target a Fresh agent.

        Parameters:
            None.

        Returns:
            True when the assigned agent ID is configured.

        Edge cases:
            Missing agent ID means the app cannot safely infer who "me" is.
        """
        return bool(self.fresh_assigned_agent_id.strip())

    @property
    def has_clickup_credentials(self) -> bool:
        """Return whether ClickUp integration credentials are configured.

        Parameters:
            None.

        Returns:
            True when API key, team ID, and list ID are present.

        Edge cases:
            Missing list ID disables task creation but mock data remains available.
        """
        return bool(self.clickup_api_key.strip() and self.clickup_team_id.strip() and self.clickup_list_id.strip())

    @property
    def has_openai_key(self) -> bool:
        """Return whether OpenAI credentials are configured.

        Parameters:
            None.

        Returns:
            True when OpenAI API key is present.

        Edge cases:
            Empty key enables deterministic mock AI output.
        """
        return bool(self.openai_api_key.strip())


# Global override populated at startup from database settings.
_app_settings_override: Settings | None = None


def set_app_settings(settings: Settings) -> None:
    """Override in-memory settings, typically from database values at startup.

    Parameters:
        settings: Settings instance to use globally.

    Returns:
        None.

    Edge cases:
        Call get_settings.cache_clear() before setting when the cache may already be populated.
    """
    global _app_settings_override
    _app_settings_override = settings


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings.

    Parameters:
        None.

    Returns:
        Singleton-like Settings instance.

    Edge cases:
        Tests can clear the cache if environment overrides are required.
        Startup may populate _app_settings_override from database values.
    """
    if _app_settings_override is not None:
        return _app_settings_override
    return Settings()


def build_settings_from_overrides(base: Settings, overrides: dict[str, Any]) -> Settings:
    """Create a new Settings instance merging environment values with database overrides.

    Parameters:
        base: Base settings loaded from environment.
        overrides: Dictionary of setting key to value from database.

    Returns:
        Merged Settings instance.

    Edge cases:
        Empty string overrides are ignored so the environment value is preserved.
    """
    merged = base.model_dump()
    for key, value in overrides.items():
        if value not in (None, ""):
            merged[key] = value
    return Settings(**merged)
