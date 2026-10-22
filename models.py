from datetime import datetime, timezone

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash
import secrets
import string
from urllib.parse import urlparse
db = SQLAlchemy()
MAX_TITLE_LENGTH = 100


def _utcnow():
    return datetime.now(timezone.utc)


def validate_title(raw):
    """Return a cleaned title, or raise ValueError with a clear message."""
    if not isinstance(raw, str):
        raise ValueError("Title is required.")
    title = raw.strip()
    if not title:
        raise ValueError("Title must not be blank.")
    if len(title) > MAX_TITLE_LENGTH:
        raise ValueError(f"Title must be at most {MAX_TITLE_LENGTH} characters.")
    return title


class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(MAX_TITLE_LENGTH), nullable=False)
    done = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "done": self.done,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

MAX_URL_LENGTH = 2048
SHORT_CODE_LENGTH = 6
SHORT_CODE_ALPHABET = string.ascii_letters + string.digits


def validate_url(raw):
    """Return a cleaned URL, or raise ValueError. Only http and https links are allowed."""
    if not isinstance(raw, str):        # None, numbers or lists from the JSON API
        raise ValueError("URL is required.")
    url = raw.strip()
    if not url:
        raise ValueError("URL must not be blank.")
    if len(url) > MAX_URL_LENGTH:
        raise ValueError(f"URL must be at most {MAX_URL_LENGTH} characters.")
    if any(ch.isspace() for ch in url):
        raise ValueError("URL must not contain spaces.")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("URL must start with http:// or https:// and include a website name.")
    return url


def generate_short_code(length=SHORT_CODE_LENGTH):
    """A random code such as 'aB3xY9' (62 possible characters per position)."""
    return "".join(secrets.choice(SHORT_CODE_ALPHABET) for _ in range(length))


class Link(db.Model):
    __tablename__ = "links"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    original_url = db.Column(db.String(MAX_URL_LENGTH), nullable=False)
    short_code = db.Column(db.String(10), unique=True, nullable=False, index=True)
    clicks = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "original_url": self.original_url,
            "short_code": self.short_code,
            "clicks": self.clicks,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }