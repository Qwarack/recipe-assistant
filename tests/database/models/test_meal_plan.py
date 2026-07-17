from app.database.models.meal_plan import (
    MealPlanRecord,
)


def test_meal_plan_table_name() -> None:
    assert MealPlanRecord.__tablename__ == "meal_plans"


def test_meal_plan_has_expected_columns() -> None:
    column_names = {column.name for column in MealPlanRecord.__table__.columns}

    assert column_names == {
        "id",
        "start_date",
        "name",
        "created_at",
        "updated_at",
    }


def test_meal_plan_week_start_is_unique() -> None:
    constraints = MealPlanRecord.__table__.constraints

    unique_column_sets = {
        tuple(column.name for column in constraint.columns)
        for constraint in constraints
        if hasattr(constraint, "columns")
        and constraint.__class__.__name__ == "UniqueConstraint"
    }

    assert ("start_date",) in unique_column_sets
