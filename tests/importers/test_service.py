from collections.abc import Mapping
from typing import Any

from app.importers.service import run_import
from app.models.import_result import ImportResult, ImportStatus


class FakeImporter:
    extractor_name = "fake"

    def import_recipe(
        self,
        source: Mapping[str, Any],
    ) -> ImportResult:
        return ImportResult(
            status=ImportStatus.FAILED,
            extractor=self.extractor_name,
        )


def test_run_import_uses_supplied_importer() -> None:
    importer = FakeImporter()

    result = run_import(
        importer,
        {"title": "Ignored"},
    )

    assert result.status is ImportStatus.FAILED
    assert result.extractor == "fake"
