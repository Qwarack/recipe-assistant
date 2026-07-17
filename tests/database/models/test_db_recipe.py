from app.database.models.recipe import RecipeRecord


def test_recipe_record_table_name() -> None:
    assert RecipeRecord.__tablename__ == "recipes"


def test_recipe_record_has_expected_columns() -> None:
    column_names = {column.name for column in RecipeRecord.__table__.columns}

    assert column_names == {
        "id",
        "identifier",
        "title",
        "file_path",
        "source_url",
        "content_hash",
        "created_at",
        "updated_at",
    }
