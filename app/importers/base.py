from typing import Protocol, TypeVar, runtime_checkable

from app.models.import_result import ImportResult

SourceT = TypeVar("SourceT", contravariant=True)


@runtime_checkable
class RecipeImporter(Protocol[SourceT]):
    extractor_name: str

    def import_recipe(self, source: SourceT) -> ImportResult: ...
