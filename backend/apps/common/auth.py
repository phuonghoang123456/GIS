from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from django.conf import settings
from rest_framework import authentication


def hash_password(plain_text: str) -> str:
    return bcrypt.hashpw(plain_text.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_text: str, hashed_text: str) -> bool:
    try:
        return bcrypt.checkpw(plain_text.encode("utf-8"), hashed_text.encode("utf-8"))
    except Exception:
        return False


def generate_token(user) -> str:
    exp = datetime.now(tz=timezone.utc) + timedelta(days=settings.JWT_EXPIRES_DAYS)
    payload = {
        "userId": user.id,
        "username": user.username,
        "role": user.role,
        "exp": exp,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def verify_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except Exception:
        return None


class JWTAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get("Authorization", "")
        cookie_token = request.COOKIES.get("token")
        token = None

        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()
        elif cookie_token:
            token = cookie_token

        if not token:
            return None

        decoded = verify_token(token)
        if not decoded:
            return None

        from apps.accounts.models import User

        user = User.objects.filter(id=decoded.get("userId"), is_active=True).first()
        if not user:
            return None

        return (user, token)
