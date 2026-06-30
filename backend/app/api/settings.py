from fastapi import APIRouter, Depends

from app.api.deps import get_app_settings_repository, require_auth
from app.repositories.app_settings_repository import AppSettingsRepository
from app.schemas.settings import AppSettings
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/settings", tags=["settings"], dependencies=[Depends(require_auth)])


@router.get("", response_model=AppSettings)
async def get_settings(
    repository: AppSettingsRepository = Depends(get_app_settings_repository),
) -> AppSettings:
    """Return editable application settings.

    Parameters:
        repository: App settings repository dependency.

    Returns:
        Current editable settings.

    Edge cases:
        Missing settings return empty strings.
    """
    service = SettingsService(repository)
    return await service.get_settings()


@router.put("", response_model=AppSettings)
async def update_settings(
    settings: AppSettings,
    repository: AppSettingsRepository = Depends(get_app_settings_repository),
) -> AppSettings:
    """Update editable application settings.

    Parameters:
        settings: New settings values.
        repository: App settings repository dependency.

    Returns:
        Stored settings.

    Edge cases:
        Settings take effect after application restart.
    """
    service = SettingsService(repository)
    return await service.update_settings(settings)
