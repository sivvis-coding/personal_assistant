from app.repositories.app_settings_repository import AppSettingsRepository
from app.schemas.settings import AppSettings


class SettingsService:
    """Manage editable application settings persisted in MongoDB.

    Parameters:
        repository: App settings repository dependency.

    Returns:
        Settings service.

    Edge cases:
        Settings are merged with environment variables at startup.
    """

    def __init__(self, repository: AppSettingsRepository) -> None:
        """Initialize the settings service."""
        self._repository = repository

    async def get_settings(self) -> AppSettings:
        """Return current editable settings from the database.

        Parameters:
            None.

        Returns:
            App settings.

        Edge cases:
            Missing settings return empty strings.
        """
        stored = await self._repository.get_all()
        return AppSettings.model_validate(stored)

    async def update_settings(self, settings: AppSettings) -> AppSettings:
        """Persist editable settings.

        Parameters:
            settings: Settings to store.

        Returns:
            Stored settings.

        Edge cases:
            Settings take effect after application restart because the core Settings object is loaded once.
        """
        for key, value in settings.model_dump().items():
            await self._repository.set(key, value)
        return settings
