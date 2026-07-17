from app.database.models.meal_plan_entry import (
    MealPlanEntryRecord,
)


def test_meal_plan_entry_table_name() -> None:
    assert MealPlanEntryRecord.__tablename__ == "meal_plan_entries"


def test_meal_plan_entry_has_expected_columns() -> None:
    column_names = {column.name for column in MealPlanEntryRecord.__table__.columns}

    assert column_names == {
        "id",
        "meal_plan_id",
        "recipe_id",
        "planned_date",
        "meal_type",
        "servings",
        "notes",
        "source",
        "source_entry_id",
        "created_at",
        "updated_at",
    }


def test_meal_plan_entry_slot_is_unique() -> None:
    constraints = MealPlanEntryRecord.__table__.constraints

    unique_column_sets = {
        tuple(column.name for column in constraint.columns)
        for constraint in constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }

    assert (
        "meal_plan_id",
        "planned_date",
        "meal_type",
    ) in unique_column_sets
