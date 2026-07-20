
import os
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
database_url = os.getenv("DATABASE_URL")

if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)


class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-me")

    SQLALCHEMY_DATABASE_URI = (
        database_url
        or f"sqlite:///{os.path.join(BASE_DIR, 'aloksaar.db')}"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

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
