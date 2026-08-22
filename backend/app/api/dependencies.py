"""FastAPI dependency-injection wiring. Swapping the pricing/catalog provider
(mock -> live GCP) only requires changing `get_catalog_provider` /
`get_pricing_provider` in the `app.catalog.dependency` / `app.pricing.dependency`
modules - routers and services never construct providers themselves.

Also wires up Phase 3 persistence/auth: `get_db` (DB session per request),
`get_current_user` (JWT -> UserModel), and `require_roles` (RBAC gate)."""
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.catalog.base import CatalogProvider
from app.catalog.dependency import get_catalog_provider
from app.core.config import Settings, get_settings
from app.core.exceptions import ForbiddenError, NotAuthenticatedError
from app.core.security import TokenError, decode_access_token
from app.db.models import UserModel
from app.db.session import get_db
from app.pricing.base import PricingProvider
from app.pricing.dependency import get_pricing_provider
from app.repositories.estimate_repository import EstimateVersionRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.services.estimation_service import EstimationService
from app.services.optimization_service import OptimizationService
from app.services.project_service import ProjectService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_estimation_service(
    catalog: CatalogProvider = Depends(get_catalog_provider),
    pricing: PricingProvider = Depends(get_pricing_provider),
    settings: Settings = Depends(get_settings),
) -> EstimationService:
    return EstimationService(catalog=catalog, pricing_provider=pricing, settings=settings)


def get_optimization_service(
    estimation_service: EstimationService = Depends(get_estimation_service),
    settings: Settings = Depends(get_settings),
) -> OptimizationService:
    return OptimizationService(estimation_service=estimation_service, settings=settings)


def get_auth_service(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> AuthService:
    return AuthService(UserRepository(db), settings)


def get_project_service(
    db: Session = Depends(get_db),
    estimation_service: EstimationService = Depends(get_estimation_service),
) -> ProjectService:
    return ProjectService(
        project_repo=ProjectRepository(db),
        estimate_repo=EstimateVersionRepository(db),
        estimation_service=estimation_service,
    )


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> UserModel:
    if token is None:
        raise NotAuthenticatedError()
    try:
        payload = decode_access_token(token, settings)
    except TokenError as exc:
        raise NotAuthenticatedError("Invalid or expired token.") from exc

    user = UserRepository(db).get_by_id(int(payload["sub"]))
    if user is None or not user.is_active:
        raise NotAuthenticatedError("User no longer exists or is inactive.")
    return user


def get_current_user_optional(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> UserModel | None:
    """Like `get_current_user`, but returns None instead of 401 when there's
    no (or an invalid) token - for endpoints that work anonymously but still
    need to know the caller's role *if* they're logged in (e.g. hiding the
    admin-only audit log from the stateless report export)."""
    if token is None:
        return None
    try:
        payload = decode_access_token(token, settings)
    except TokenError:
        return None
    return UserRepository(db).get_by_id(int(payload["sub"]))


def require_roles(*roles: str):
    """Dependency factory: `Depends(require_roles("admin"))` restricts an
    endpoint to the given roles (in addition to requiring authentication)."""

    def _check(user: UserModel = Depends(get_current_user)) -> UserModel:
        if user.role not in roles:
            raise ForbiddenError(f"This action requires one of roles {roles}, but you have '{user.role}'.")
        return user

    return _check
