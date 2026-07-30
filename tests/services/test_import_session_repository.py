import asyncio
from uuid import uuid4

import pytest
from app.models.import_result import ImportResult, ImportStatus
from app.models.import_session import (
    ImportProcessingStatus,
    ImportSource,
)
from app.models.recipe import Ingredient, Recipe, SourceType
from app.services.import_session_repository import (
    ImportAlreadyProcessingError,
    ImportPermissionError,
    ImportSessionRepository,
)


def _result() -> ImportResult:
    return ImportResult(
        status=ImportStatus.SUCCESS,
        recipe=Recipe(
            title="Soup",
            source_type=SourceType.MANUAL,
            ingredients=[Ingredient(name="water")],
            instructions=["Mix."],
        ),
    )


def test_repository_registers_source_and_candidate() -> None:
    repository = ImportSessionRepository()
    result = _result()

    session = repository.register(
        result=result,
        source=ImportSource(
            source_type=SourceType.MANUAL,
            raw_text="Soup",
        ),
    )

    assert session.import_id == result.import_id
    assert session.active_result.recipe == result.recipe
    assert session.status is ImportProcessingStatus.AWAITING_CONFIRMATION


def test_repository_enforces_import_owner() -> None:
    repository = ImportSessionRepository()
    result = _result()
    repository.register(
        result=result,
        source=ImportSource(source_type=SourceType.MANUAL, raw_text="Soup"),
        discord_user_id=123,
    )

    with pytest.raises(ImportPermissionError):
        repository.set_owner(result.import_id, 456)


def test_repository_rejects_concurrent_processing() -> None:
    repository = ImportSessionRepository()
    result = _result()
    repository.register(
        result=result,
        source=ImportSource(source_type=SourceType.MANUAL, raw_text="Soup"),
    )

    async def exercise_lock() -> None:
        async with repository.processing(result.import_id):
            with pytest.raises(ImportAlreadyProcessingError):
                async with repository.processing(result.import_id):
                    pass

    asyncio.run(exercise_lock())


def test_cancel_removes_temporary_image(tmp_path) -> None:
    image_path = tmp_path / f"{uuid4()}.jpg"
    image_path.write_bytes(b"image")
    repository = ImportSessionRepository()
    result = _result()
    repository.register(
        result=result,
        source=ImportSource(
            source_type=SourceType.IMAGE,
            temporary_file_path=image_path,
        ),
    )

    session = repository.cancel(result.import_id)

    assert session.status is ImportProcessingStatus.CANCELLED
    assert session.source.temporary_file_path is None
    assert not image_path.exists()
