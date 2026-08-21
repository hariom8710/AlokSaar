
import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

'''
class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-me")

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(BASE_DIR, 'aloksaar.db')}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- LLM provider selection ---
    # "gemini" (free tier, default) or "anthropic" (paid, no free tier)
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower()

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

    CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", os.path.join(BASE_DIR, "chroma_store"))

    DEBUG = os.getenv("FLASK_DEBUG", "1") == "1"

    '''

# Render/Heroku compatibility
def _normalize_database_url(value):
    """Normalize provider URLs and require TLS for Neon connections."""
    if not value:
        return None
    value = value.strip()
    if value.startswith("postgres://"):
        value = "postgresql://" + value[len("postgres://"):]

    parsed = urlsplit(value)
    if parsed.hostname and parsed.hostname.endswith(".neon.tech"):
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query.setdefault("sslmode", "require")
        value = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))
    return value


database_url = _normalize_database_url(os.getenv("DATABASE_URL"))

class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-me")

    SQLALCHEMY_DATABASE_URI = (
        database_url
        or f"sqlite:///{os.path.join(BASE_DIR, 'aloksaar.db')}"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "300")),
        "pool_size": int(os.getenv("DB_POOL_SIZE", "5")),
        "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "2")),
        "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", "30")),
    }

    DATABASE_URL_UNPOOLED = _normalize_database_url(
        os.getenv("DATABASE_URL_UNPOOLED") or os.getenv("NEON_DATABASE_URL_UNPOOLED")
    )
    USING_NEON = bool(database_url and ".neon.tech" in database_url)

    # ---------- LLM ----------
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower()

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

    # ---------- Vector Database ----------
    CHROMA_DB_PATH = os.getenv(
        "CHROMA_DB_PATH",
        os.path.join(BASE_DIR, "chroma_store")
    )

    DEBUG = os.getenv("FLASK_DEBUG", "1") == "1"
