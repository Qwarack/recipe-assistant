from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID


class ImportDebugStorage:
    def __init__(self, imports_path: Path) -> None:
        self.imports_path = imports_path

    def save_html(
        self,
        html: str,
        import_id: UUID,
    ) -> Path:
        self.imports_path.mkdir(
            parents=True,
            exist_ok=True,
        )

        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        short_id = str(import_id).split("-")[0]

        destination = self.imports_path / (f"{timestamp}-{short_id}.html")

        destination.write_text(
            html,
            encoding="utf-8",
        )

        return destination
