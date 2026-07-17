from app.core.config import get_settings
from app.database.engine import create_session_factory
from app.services.recipe_index_sync_service import (
    RecipeIndexSyncService,
)


def main() -> None:
    settings = get_settings()

    session_factory = create_session_factory(settings.database_path)

    with session_factory() as session:
        service = RecipeIndexSyncService(
            session=session,
            recipes_path=settings.recipes_path,
        )

        synced_count = service.sync_all()

    print(f"Gesynchroniseerde recepten: {synced_count}")


if __name__ == "__main__":
    main()
