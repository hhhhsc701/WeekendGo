from app.core.settings import get_settings
from app.db.database import initialize_database


def main() -> None:
    settings = get_settings()
    initialize_database(settings.database_path)
    print(f"Initialized database at {settings.database_path}")


if __name__ == "__main__":
    main()
