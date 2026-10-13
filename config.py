import os
from pathlib import Path

from dotenv import load_dotenv

# Read variables from a .env file next to this file (local development).
# Variables already set in the real environment (Docker, CI, AWS) take priority.
load_dotenv(Path(__file__).resolve().parent / ".env", override=False)


def normalise_database_url(url):
    """Make a PostgreSQL URL usable by SQLAlchemy (postgres:// is no longer accepted)."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg2://" + url[len(prefix):]
    return url


class Config:
    # Set DATABASE_URL in the environment for staging/production.
    # The fallback is only for local development.
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Signs the login cookie. Real servers must set the SECRET_KEY environment variable.
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")