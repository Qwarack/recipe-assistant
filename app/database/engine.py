from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def create_sqlite_engine(database_path: Path):
    database_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    database_url = f"sqlite:///{database_path.as_posix()}"

    return create_engine(
        database_url,
        connect_args={
            "check_same_thread": False,
        },
    )


def create_session_factory(
    database_path: Path,
) -> sessionmaker[Session]:
    engine = create_sqlite_engine(database_path)

    return sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )


def get_session(
    session_factory: sessionmaker[Session],
) -> Generator[Session, None, None]:
    session = session_factory()

    try:
        yield session
    finally:
        session.close()
