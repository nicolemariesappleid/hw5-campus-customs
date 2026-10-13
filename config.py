"""Shared settings for every part of the Campus Customs project.

The MCP server, the backend, and every agent import from here, so the
database path and the AI model are set in exactly one place.
"""
import os
import sqlite3
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader (no extra dependency). Real env vars win."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(PROJECT_DIR / ".env")

# --- Database ---------------------------------------------------------------
# ORIGINAL_DB is the pristine copy: never written to, used only for resets.
# DB_PATH is the working copy that the MCP server and backend read and write.
ORIGINAL_DB = PROJECT_DIR / "data" / "campus_customs.db"
DB_PATH = PROJECT_DIR / "data" / "campus_customs_new.db"

if DB_PATH.resolve() == ORIGINAL_DB.resolve():
    raise RuntimeError("DB_PATH must point at the working copy, not the original.")


def get_connection() -> sqlite3.Connection:
    """Open the working-copy database. Use this everywhere instead of sqlite3.connect."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# --- AI (Portkey) -----------------------------------------------------------
# Every agent uses the same model through Portkey. Do not override per agent.
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"
MODEL = "gpt-6-luna"


def get_portkey_api_key() -> str:
    key = os.environ.get("PORTKEY_API_KEY")
    if not key:
        raise RuntimeError(
            "PORTKEY_API_KEY is not set. Export it in your shell or put it in hw5/.env."
        )
    return key


def portkey_model():
    """The one model every agent uses: gpt-6-luna through Portkey (PydanticAI model object)."""
    from openai import AsyncOpenAI
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider

    key = get_portkey_api_key()
    client = AsyncOpenAI(base_url=PORTKEY_BASE_URL, api_key=key,
                         default_headers={"x-portkey-api-key": key})
    return OpenAIChatModel(MODEL, provider=OpenAIProvider(openai_client=client))
