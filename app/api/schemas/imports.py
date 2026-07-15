from pathlib import Path
from uuid import UUID

from app.models.import_result import ImportStatus, ImportWarning
from pydantic import BaseModel, HttpUrl


class WebsiteImportRequest(BaseModel):
    url: HttpUrl
    force: bool = False


class WebsiteImportResponse(BaseModel):
    import_id: UUID
    status: ImportStatus
    destination: Path | None = None
    warnings: list[ImportWarning]
