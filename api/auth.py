import os
from datetime import datetime, timedelta, timezone

import bcrypt as _bcrypt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

load_dotenv()

_ALGORITHM = "HS256"
_bearer = HTTPBearer()


def _jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET", "")
    if not secret:
        raise RuntimeError("JWT_SECRET não definido no .env")
    return secret


def _expire_hours() -> int:
    return int(os.getenv("JWT_EXPIRE_HOURS", "8"))


def criar_token(username: str) -> str:
    expira = datetime.now(timezone.utc) + timedelta(hours=_expire_hours())
    payload = {"sub": username, "exp": expira}
    return jwt.encode(payload, _jwt_secret(), algorithm=_ALGORITHM)


def verificar_credenciais(username: str, password: str) -> bool:
    admin_user = os.getenv("ADMIN_USERNAME", "admin")
    admin_hash = os.getenv("ADMIN_PASSWORD_HASH", "")
    if username != admin_user or not admin_hash:
        return False
    return _bcrypt.checkpw(password.encode(), admin_hash.encode())


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> str:
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido ou expirado.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(credentials.credentials, _jwt_secret(), algorithms=[_ALGORITHM])
        username: str | None = payload.get("sub")
        if not username:
            raise exc
    except JWTError:
        raise exc
    return username
