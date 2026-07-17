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
        "status",
        "generation_seed",
        "generated_at",
        "generation_config",
        "created_by",
        "activated_by",
        "generation_source",
        "created_at",
        "updated_at",
    }


def test_active_meal_plan_week_start_is_unique() -> None:
    index = next(
        item
        for item in MealPlanRecord.__table__.indexes
        if item.name == "uq_active_meal_plan_start_date"
    )

    assert index.unique is True
    assert tuple(column.name for column in index.columns) == ("start_date",)
    assert str(index.dialect_options["sqlite"]["where"]) == "status = 'active'"
