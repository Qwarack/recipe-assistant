from pathlib import Path
from uuid import uuid4

from app.services.import_debug_storage import (
    ImportDebugStorage,
)


def test_saves_raw_html(
    tmp_path: Path,
) -> None:
    import_id = uuid4()
    storage = ImportDebugStorage(tmp_path)

    destination = storage.save_html(
        html="<html><body>test</body></html>",
        import_id=import_id,
    )

    assert destination.exists()
    assert destination.suffix == ".html"
    assert str(import_id).split("-")[0] in destination.name
    assert destination.read_text(encoding="utf-8") == "<html><body>test</body></html>"
