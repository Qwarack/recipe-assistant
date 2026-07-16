from pathlib import Path

from app.api import uploads as uploads_api
from app.importers.manual_text import ManualTextRecipeImporter
from app.main import app
from app.services.markdown_renderer import RecipeMarkdownRenderer
from app.services.recipe_duplicate_detector import RecipeDuplicateDetector
from app.services.recipe_import_service import RecipeImportService
from app.services.recipe_storage import RecipeStorage
from fastapi.testclient import TestClient


def test_markdown_upload_preview_uses_file_importer() -> None:
    markdown = """---
title: Pasta Carbonara
---

# Pasta Carbonara

## Ingrediënten

- 400 g spaghetti

## Bereiding

1. Kook de spaghetti.
""".encode()

    with TestClient(app) as client:
        response = client.post(
            "/imports/upload/preview",
            files={"file": ("pasta.md", markdown, "text/markdown")},
        )

    assert response.status_code == 200
    assert response.json()["recipe"]["title"] == "Pasta Carbonara"


def test_html_upload_preview_uses_file_importer(load_fixture) -> None:
    html = load_fixture("websites/basic_recipe.html")

    with TestClient(app) as client:
        response = client.post(
            "/imports/upload/preview",
            files={"file": ("pasta.html", html, "text/html")},
        )

    assert response.status_code == 200
    assert response.json()["recipe"]["title"] == "Pasta Carbonara"


def test_text_upload_preview_uses_text_importer() -> None:
    text = """Tomato Soup

Ingredients
- 500 ml water

Instructions
1. Mix everything.
"""

    with TestClient(app) as client:
        response = client.post(
            "/imports/upload/preview",
            files={"file": ("soup.txt", text, "text/plain")},
        )

    assert response.status_code == 200
    assert response.json()["recipe"]["title"] == "Tomato Soup"


def test_preview_markdown_upload() -> None:
    markdown = """---
title: Pasta Carbonara
servings: 4
---

# Pasta Carbonara

## Ingrediënten

- 400 g spaghetti
- 4 eieren

## Bereiding

1. Kook de spaghetti.
2. Meng de eieren.
"""

    with TestClient(app) as client:
        response = client.post(
            "/imports/upload/preview",
            files={
                "file": (
                    "pasta-carbonara.md",
                    markdown.encode("utf-8"),
                    "text/markdown",
                )
            },
        )

    assert response.status_code == 200

    body = response.json()

    assert body["destination"] is None
    assert body["recipe"]["title"] == "Pasta Carbonara"
    assert body["recipe"]["ingredient_count"] == 2
    assert body["recipe"]["instruction_count"] == 2


def test_preview_text_upload() -> None:
    text = """Tomatensoep

Ingrediënten:
- 1 kg tomaten
- 1 ui

Bereiding:
1. Snijd de groenten.
2. Kook alles gaar.
"""

    with TestClient(app) as client:
        response = client.post(
            "/imports/upload/preview",
            files={
                "file": (
                    "tomatensoep.txt",
                    text.encode("utf-8"),
                    "text/plain",
                )
            },
        )

    assert response.status_code == 200
    assert response.json()["destination"] is None


def test_preview_upload_rejects_unsupported_extension() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/imports/upload/preview",
            files={
                "file": (
                    "recept.exe",
                    b"not a recipe",
                    "application/octet-stream",
                )
            },
        )

    assert response.status_code == 415
    assert response.json() == {"detail": "Unsupported recipe file type"}


def test_preview_upload_rejects_empty_file() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/imports/upload/preview",
            files={
                "file": (
                    "leeg.md",
                    b"",
                    "text/markdown",
                )
            },
        )

    assert response.status_code == 400
    assert response.json() == {"detail": "Uploaded file is empty"}


def test_upload_import_creates_markdown_file(tmp_path: Path) -> None:
    recipes_path = tmp_path / "recipes"
    recipes_path.mkdir()

    storage = RecipeStorage(
        recipes_path=recipes_path,
        renderer=RecipeMarkdownRenderer(),
    )
    service = RecipeImportService(
        importer=ManualTextRecipeImporter(),
        storage=storage,
        duplicate_detector=RecipeDuplicateDetector(recipes_path),
    )

    app.dependency_overrides[uploads_api.create_import_service] = lambda: service

    markdown = """---
title: Pasta Carbonara
servings: 4
---

# Pasta Carbonara

## Ingrediënten

- 400 g spaghetti
- 4 eieren

## Bereiding

1. Kook de spaghetti.
2. Meng de eieren.
"""

    try:
        with TestClient(app) as client:
            response = client.post(
                "/imports/upload",
                files={
                    "file": (
                        "pasta-carbonara.md",
                        markdown.encode("utf-8"),
                        "text/markdown",
                    )
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200

    body = response.json()

    assert body["destination"] is not None

    created_files = list(recipes_path.glob("*.md"))

    assert len(created_files) == 1
    created_markdown = created_files[0].read_text(encoding="utf-8")

    assert "Pasta Carbonara" in created_markdown
    assert "400 g spaghetti" in created_markdown
