from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_alembic_upgrade_adds_automatic_planning_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "migration.db"
    config = Config("alembic.ini")
    config.set_main_option(
        "sqlalchemy.url",
        f"sqlite:///{database_path.as_posix()}",
    )

    command.upgrade(config, "head")

    inspector = inspect(create_engine(f"sqlite:///{database_path.as_posix()}"))
    recipe_columns = {column["name"] for column in inspector.get_columns("recipes")}
    plan_columns = {column["name"] for column in inspector.get_columns("meal_plans")}
    entry_columns = {
        column["name"] for column in inspector.get_columns("meal_plan_entries")
    }
    plan_indexes = {
        index["name"]: index for index in inspector.get_indexes("meal_plans")
    }

    assert {
        "tags",
        "meal_types",
        "preparation_time_minutes",
        "difficulty",
        "vegetarian",
        "last_planned_at",
    }.issubset(recipe_columns)
    assert {"status", "generation_seed", "generation_config"}.issubset(plan_columns)
    assert {"source", "source_entry_id"}.issubset(entry_columns)
    assert plan_indexes["uq_active_meal_plan_start_date"]["unique"] == 1
