"""Registration, authentication, and token issuance. Depends only on
`UserRepository` (repository pattern) and `Settings` - no direct DB access."""
from app.core.config import Settings
from app.core.exceptions import ForbiddenError, InvalidCredentialsError, DuplicateEmailError
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import UserModel
from app.domain.auth import UserCreate, UserRole
from app.repositories.user_repository import UserRepository

# Roles a completely unauthenticated visitor is allowed to grant themselves
# via POST /api/v1/auth/register. "admin" is deliberately excluded: it grants
# system-wide visibility into every user's projects and estimates (see
# ProjectService's `role == ADMIN_ROLE` bypass of the ownership check), so
# self-service admin signup would be a straight-up privilege-escalation hole
# (any anonymous caller could grant themselves org-wide read access by
# passing role="admin" in the register payload - found during a live QA
# pass, not caught by the earlier unit test suite because no test had
# actually asserted on this). There is currently no admin-only "create user
# with an elevated role" endpoint; provisioning a real admin account today
# means promoting a row directly in the database.
_PUBLIC_SELF_SERVE_ROLES = {UserRole.CUSTOMER, UserRole.CONSULTANT}


class AuthService:
    def __init__(self, user_repo: UserRepository, settings: Settings):
        self.user_repo = user_repo
        self.settings = settings

    def register(self, data: UserCreate) -> UserModel:
        if self.user_repo.get_by_email(data.email) is not None:
            raise DuplicateEmailError()
        if data.role not in _PUBLIC_SELF_SERVE_ROLES:
            raise ForbiddenError(
                f"Self-service registration cannot grant the '{data.role.value}' role. "
                "Admin accounts must be provisioned by an existing administrator."
            )
        return self.user_repo.create(
            email=data.email,
            hashed_password=hash_password(data.password),
            full_name=data.full_name,
            role=data.role.value,
        )

    def authenticate(self, email: str, password: str) -> UserModel:
        user = self.user_repo.get_by_email(email)
        if user is None or not user.is_active or not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError()
        return user

    def create_token(self, user: UserModel) -> str:
        return create_access_token(subject=str(user.id), role=user.role, settings=self.settings)
