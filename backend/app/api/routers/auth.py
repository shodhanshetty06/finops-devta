"""Registration, login, and "who am I" endpoints."""
from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from app.api.dependencies import get_auth_service, get_current_user
from app.db.models import UserModel
from app.domain.auth import Token, UserCreate, UserRead
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


@router.post("/register", response_model=UserRead, status_code=201, summary="Create a new user account")
def register(data: UserCreate, auth_service: AuthService = Depends(get_auth_service)):
    return auth_service.register(data)


@router.post(
    "/login", response_model=Token,
    summary="Log in and receive a JWT access token",
    description="Uses the OAuth2 password flow (username=email) so the Swagger UI 'Authorize' button works directly.",
)
def login(form_data: OAuth2PasswordRequestForm = Depends(), auth_service: AuthService = Depends(get_auth_service)):
    user = auth_service.authenticate(form_data.username, form_data.password)
    token = auth_service.create_token(user)
    return Token(access_token=token)


@router.get("/me", response_model=UserRead, summary="Get the currently authenticated user")
def me(current_user: UserModel = Depends(get_current_user)):
    return current_user
