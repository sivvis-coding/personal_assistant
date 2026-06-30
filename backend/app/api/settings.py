import logging

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_app_settings_repository, get_llm_provider, require_auth
from app.core.llm.provider import LLMProvider
from app.repositories.app_settings_repository import AppSettingsRepository
from app.schemas.settings import (
    AppSettings,
    ClickUpFieldSuggestion,
    ClickUpSuggestRequest,
    ClickUpSuggestResponse,
)
from app.services.settings_service import SettingsService

logger = logging.getLogger(__name__)

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


@router.post("/suggest/clickup", response_model=ClickUpSuggestResponse)
async def suggest_clickup_descriptions(
    request: ClickUpSuggestRequest,
    llm_provider: LLMProvider = Depends(get_llm_provider),
) -> ClickUpSuggestResponse:
    """Use AI to suggest routing and field descriptions for a ClickUp list.

    Parameters:
        request: List name, existing description, and fields to describe.
        llm_provider: LLM provider dependency.

    Returns:
        AI-generated routing description and per-field descriptions.

    Edge cases:
        Returns empty strings if the LLM fails or no fields are provided.
    """
    fields_text = "\n".join(
        f"  - id={f.field_id}, name={f.field_name!r}, type={f.type_ or 'unknown'}"
        for f in request.fields
    ) or "  (no custom fields)"

    prompt = (
        f"You are a ClickUp configuration assistant helping an IT team set up their project management tool.\n\n"
        f"List name: {request.list_name!r}\n"
        f"Existing routing description: {request.existing_description!r}\n\n"
        f"Custom fields:\n{fields_text}\n\n"
        f"Generate two things:\n"
        f"1. A concise routing_description (1-2 sentences in Spanish) that tells an AI agent WHEN to use this list "
        f"   (e.g. 'Usa esta lista para reportar bugs y errores de producción.').\n"
        f"2. For each custom field, a concise description (1 sentence in Spanish) telling the AI agent what VALUE to put there.\n\n"
        f"Return a JSON object with:\n"
        f"  routing_description: string\n"
        f"  field_descriptions: array of {{field_id: string, description: string}}\n\n"
        f"Be specific and practical. Use the field name and type to infer its purpose."
    )

    try:
        result = await llm_provider.complete_structured(prompt)
    except Exception as exc:
        logger.error("AI suggestion failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"AI suggestion failed: {exc}") from exc

    routing = str(result.get("routing_description", ""))
    raw_fields = result.get("field_descriptions", [])
    if not isinstance(raw_fields, list):
        raw_fields = []

    field_suggestions = [
        ClickUpFieldSuggestion(
            field_id=str(item.get("field_id", "")),
            description=str(item.get("description", "")),
        )
        for item in raw_fields
        if isinstance(item, dict) and item.get("field_id")
    ]

    return ClickUpSuggestResponse(
        routing_description=routing,
        field_descriptions=field_suggestions,
    )


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
