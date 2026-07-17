from pathlib import Path

from app.database.engine import (
    create_session_factory,
    create_sqlite_engine,
)
from sqlalchemy import text


def test_create_sqlite_engine_creates_database_directory(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "database" / "app.db"

    engine = create_sqlite_engine(database_path)

    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))

        assert result.scalar_one() == 1

    assert database_path.parent.exists()


def test_session_factory_creates_working_session(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "app.db"

    session_factory = create_session_factory(database_path)

    with session_factory() as session:
        result = session.execute(text("SELECT 1"))

        assert result.scalar_one() == 1
