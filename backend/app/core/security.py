"""Password hashing and JWT helpers. Uses `bcrypt` directly (not passlib) to
avoid passlib/bcrypt version-compatibility warnings, and `PyJWT` for tokens -
both are small, well-audited, single-purpose dependencies."""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import Settings, get_settings


def hash_password(password: str, *, rounds: int | None = None) -> str:
    if rounds is None:
        rounds = get_settings().bcrypt_rounds
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=rounds)).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(*, subject: str, role: str, settings: Settings) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


class TokenError(Exception):
    pass


def decode_access_token(token: str, settings: Settings) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc
