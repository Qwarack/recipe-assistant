from app.database.base import Base
from sqlalchemy.orm import DeclarativeBase


def test_base_is_declarative_base() -> None:
    assert issubclass(Base, DeclarativeBase)
