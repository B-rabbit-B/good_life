from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.auth import service
from app.auth.deps import get_current_user
from app.auth.models import User
from app.auth.schemas import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.db import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", status_code=201, response_model=UserOut)
def register(body: RegisterRequest, db: Annotated[Session, Depends(get_db)]) -> User:
    return service.register_user(db, body.username, body.password)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Annotated[Session, Depends(get_db)]) -> TokenResponse:
    return TokenResponse(access_token=service.login(db, body.username, body.password))


@router.post("/logout", status_code=204)
def logout(
    user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]
) -> Response:
    service.logout(db, user)
    return Response(status_code=204)


@router.get("/me", response_model=UserOut)
def me(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user
