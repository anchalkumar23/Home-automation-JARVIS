from pathlib import Path

from app.config import Settings


def _fake_settings() -> Settings:
    return Settings(
        host="127.0.0.1",
        port=8000,
        allowed_origins=[],
        provider="auto",
        openai_api_key="",
        openai_model="",
        groq_api_key="",
        groq_model="",
        groq_whisper_model="",
        google_client_id="test-client-id",
        google_client_secret="test-secret",
        google_redirect_uri="http://127.0.0.1:8000/api/gmail/callback",
        tavily_api_key="",
        youtube_api_key="",
        finnhub_api_key="",
        tcl_tv_ip="",
        tcl_tv_mac="",
        samsung_tv_ip="",
        samsung_tv_mac="",
        lg_tv_ip="",
        lg_tv_mac="",
        api_key="",
        token_encryption_key="",
        database_path=Path("unused.db"),
    )


def test_build_auth_url_includes_client_id_and_scope():
    from app.services.google_auth import build_auth_url

    url = build_auth_url(_fake_settings())

    assert "accounts.google.com" in url
    assert "client_id=test-client-id" in url
    assert "gmail.send" in url
    assert "calendar.events" in url
