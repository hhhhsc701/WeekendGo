from app.core.settings import Settings


def test_cors_origins_accepts_single_origin_string() -> None:
    settings = Settings(CORS_ORIGINS="http://localhost:3100", FRONTEND_PORT=3100)

    assert settings.cors_origins == [
        "http://localhost:3100",
        "http://127.0.0.1:3100",
        "http://0.0.0.0:3100",
    ]


def test_cors_origins_accepts_comma_separated_origins() -> None:
    settings = Settings(CORS_ORIGINS="http://example.test, http://localhost:3100", FRONTEND_PORT=3100)

    assert settings.cors_origins == [
        "http://example.test",
        "http://localhost:3100",
        "http://127.0.0.1:3100",
        "http://0.0.0.0:3100",
    ]
