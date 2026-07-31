from datetime import datetime
from pathlib import Path
from uuid import UUID

from app.models.import_result import ImportStatus, ImportWarning
from app.models.import_session import AIParseReason, RecipeImportMetadata
from pydantic import BaseModel, Field, HttpUrl


class RecipePreview(BaseModel):
    title: str
    servings: int | None = None
    prep_time_minutes: int | None = None
    cook_time_minutes: int | None = None
    total_time_minutes: int | None = None
    ingredient_count: int
    instruction_count: int
    source_url: str | None = None


class WebsiteImportRequest(BaseModel):
    url: HttpUrl
    force: bool = False


class ManualImportRequest(BaseModel):
    text: str = Field(min_length=1)
    force: bool = False


class AIReparseRequest(BaseModel):
    reason: AIParseReason
    discord_user_id: int | None = None


class AIEnrichmentRequest(BaseModel):
    discord_user_id: int | None = None


class WebsiteImportResponse(BaseModel):
    import_id: UUID
    created_at: datetime
    status: ImportStatus
    destination: Path | None = None
    recipe: RecipePreview | None = None
    warnings: list[ImportWarning]
    metadata: RecipeImportMetadata | None = None
    ai_enabled: bool = False
