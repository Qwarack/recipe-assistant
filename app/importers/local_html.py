from pathlib import Path

from app.importers.website import WebsiteRecipeImporter
from app.models.import_result import (
    ImportResult,
    ImportStatus,
    ImportWarning,
)


class StaticHtmlClient:
    def __init__(self, html: str) -> None:
        self.html = html

    def get_text(self, url: str) -> str:
        return self.html


class LocalHtmlRecipeImporter:
    extractor_name = "local-html"

    def import_recipe(self, source: Path) -> ImportResult:
        if not source.exists():
            return ImportResult(
                status=ImportStatus.FAILED,
                warnings=[
                    ImportWarning(
                        code="html_file_not_found",
                        message=f"HTML file does not exist: {source}",
                    )
                ],
                raw_input_reference=str(source),
            )

        if not source.is_file():
            return ImportResult(
                status=ImportStatus.FAILED,
                warnings=[
                    ImportWarning(
                        code="html_path_not_file",
                        message=f"HTML path is not a file: {source}",
                    )
                ],
                raw_input_reference=str(source),
            )

        if source.suffix.casefold() not in {".html", ".htm"}:
            return ImportResult(
                status=ImportStatus.FAILED,
                warnings=[
                    ImportWarning(
                        code="unsupported_html_file_type",
                        message=(
                            "Expected an .html or .htm file, "
                            f"received: {source.suffix or '<none>'}"
                        ),
                    )
                ],
                raw_input_reference=str(source),
            )

        try:
            html = source.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return ImportResult(
                status=ImportStatus.FAILED,
                warnings=[
                    ImportWarning(
                        code="html_file_encoding_error",
                        message=("The HTML file could not be read as UTF-8."),
                    )
                ],
                raw_input_reference=str(source),
            )
        except OSError as exc:
            return ImportResult(
                status=ImportStatus.FAILED,
                warnings=[
                    ImportWarning(
                        code="html_file_read_error",
                        message=f"Could not read the HTML file: {exc}",
                    )
                ],
                raw_input_reference=str(source),
            )

        synthetic_url = f"https://local-file.example/{source.name}"

        importer = WebsiteRecipeImporter(StaticHtmlClient(html))

        result = importer.import_recipe(synthetic_url)

        return result.model_copy(
            update={
                "extractor": self.extractor_name,
                "raw_input_reference": str(source),
            }
        )
