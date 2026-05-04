from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from api.auth import criar_token, verificar_credenciais

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest) -> TokenResponse:
    if not verificar_credenciais(body.username, body.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha incorretos.",
        )
    return TokenResponse(access_token=criar_token(body.username))
