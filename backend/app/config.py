from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
ENV_FILE = BASE_DIR / ".env"


def load_dotenv() -> None:
    if not ENV_FILE.exists():
        return

    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip().strip('"').strip("'")


def parse_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    allowed_origins: list[str]
    provider: str
    openai_api_key: str
    openai_model: str
    groq_api_key: str
    groq_model: str
    groq_whisper_model: str
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str
    tavily_api_key: str
    youtube_api_key: str
    finnhub_api_key: str
    tcl_tv_ip: str
    tcl_tv_mac: str
    samsung_tv_ip: str
    samsung_tv_mac: str
    lg_tv_ip: str
    lg_tv_mac: str
    api_key: str
    token_encryption_key: str
    database_path: Path


def get_settings() -> Settings:
    load_dotenv()
    origins = os.getenv(
        "JARVIS_ALLOWED_ORIGINS",
        "http://localhost:3000,http://localhost:3001,http://127.0.0.1:3000,http://127.0.0.1:3001",
    )
    return Settings(
        host=os.getenv("JARVIS_HOST", "127.0.0.1"),
        port=int(os.getenv("JARVIS_PORT", "8000")),
        allowed_origins=parse_csv(origins),
        provider=os.getenv("JARVIS_PROVIDER", "auto").lower(),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5.4-mini"),
        groq_api_key=os.getenv("GROQ_API_KEY", ""),
        groq_model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        groq_whisper_model=os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo"),
        google_client_id=os.getenv("GOOGLE_CLIENT_ID", ""),
        google_client_secret=os.getenv("GOOGLE_CLIENT_SECRET", ""),
        google_redirect_uri=os.getenv("GOOGLE_REDIRECT_URI", "http://127.0.0.1:8000/api/gmail/callback"),
        tavily_api_key=os.getenv("TAVILY_API_KEY", ""),
        youtube_api_key=os.getenv("YOUTUBE_API_KEY", ""),
        finnhub_api_key=os.getenv("FINNHUB_API_KEY", ""),
        tcl_tv_ip=os.getenv("TCL_TV_IP", ""),
        tcl_tv_mac=os.getenv("TCL_TV_MAC", ""),
        samsung_tv_ip=os.getenv("SAMSUNG_TV_IP", ""),
        samsung_tv_mac=os.getenv("SAMSUNG_TV_MAC", ""),
        lg_tv_ip=os.getenv("LG_TV_IP", ""),
        lg_tv_mac=os.getenv("LG_TV_MAC", ""),
        api_key=os.getenv("JARVIS_API_KEY", ""),
        token_encryption_key=os.getenv("TOKEN_ENCRYPTION_KEY", ""),
        database_path=DATA_DIR / "jarvis.db",
    )
