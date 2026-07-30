from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.import_result import ImportResult
from app.models.recipe import SourceType


class ParseMethod(StrEnum):
    NORMAL = "normal"
    AI_TEXT = "ai_text"
    AI_IMAGE = "ai_image"
    AI_REPARSE = "ai_reparse"


class ValueOrigin(StrEnum):
    SOURCE = "source"
    NORMAL_PARSER = "normal_parser"
    AI_EXTRACTED = "ai_extracted"
    AI_ESTIMATED = "ai_estimated"
    USER = "user"


class AIParseReason(StrEnum):
    NORMAL_PARSE_FAILED = "normal_parse_failed"
    USER_REQUESTED_REPARSE = "user_requested_reparse"
    IMAGE_INPUT = "image_input"
    MISSING_FIELDS = "missing_fields"


class ImportProcessingStatus(StrEnum):
    RECEIVED = "received"
    PROCESSING_NORMAL = "processing_normal"
    NORMAL_PARSE_FAILED = "normal_parse_failed"
    PROCESSING_AI = "processing_ai"
    AI_PARSE_FAILED = "ai_parse_failed"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    SAVED = "saved"
    CANCELLED = "cancelled"


class ImportSource(BaseModel):
    source_type: SourceType
    source_url: str | None = None
    raw_text: str | None = None
    temporary_file_path: Path | None = None
    original_filename: str | None = None
    content_type: str | None = None

    @model_validator(mode="after")
    def validate_source_reference(self) -> "ImportSource":
        if not any(
            (
                self.source_url,
                self.raw_text,
                self.temporary_file_path,
            )
        ):
            raise ValueError("An import source reference is required")
        return self


class ParseAttempt(BaseModel):
    attempt_number: int = Field(ge=1)
    method: ParseMethod
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    success: bool = False
    model: str | None = None
    error_code: str | None = None
    warnings: list[str] = Field(default_factory=list)


class RecipeImportMetadata(BaseModel):
    parse_method: ParseMethod = ParseMethod.NORMAL
    parser_name: str | None = None
    ai_model: str | None = None
    extracted_fields: list[str] = Field(default_factory=list)
    estimated_fields: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    normal_parser_error: str | None = None
    attempts: list[ParseAttempt] = Field(default_factory=list)


class ImportSession(BaseModel):
    import_id: UUID
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    discord_user_id: int | None = None
    source: ImportSource
    status: ImportProcessingStatus = ImportProcessingStatus.RECEIVED
    active_result: ImportResult
    previous_results: list[ImportResult] = Field(default_factory=list)
    metadata: RecipeImportMetadata = Field(default_factory=RecipeImportMetadata)
