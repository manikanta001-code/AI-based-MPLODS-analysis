"""
auth.py
─────────
JWT authentication for the 4 dashboard roles: ministry, state, mp, district.

WHY FIXED DEMO ACCOUNTS INSTEAD OF A SCOPE-PICKER AT LOGIN
  The raw data has no user/login table — MPLADS doesn't ship one, and
  inventing one fake account per MP (543) or per district (718) isn't
  practical. Instead there are 4 fixed demo accounts (config.DEMO_USERS_RAW),
  each already pre-scoped to a REAL, interesting entity in the dataset
  (chosen deliberately — see config.py comment — so the demo has something
  to show immediately: state_up covers the largest state, mp_priya_saroj
  is an MP with 377 real High-risk flagged works, district_jaunpur is the
  largest single district). This is the standard shape a real deployment
  would have too (one login per state/MP/district office) — we're just
  seeding it with 4 accounts instead of hundreds.

  The scope is embedded in the JWT ("scope" claim) and every role-scoped
  router (see db_utils.enforce_scope) filters strictly by it — the
  mp_priya_saroj token can only ever see Priya Saroj's own works, enforced
  server-side, not just hidden in the UI.

DEMO CREDENTIALS:
    ministry          / ministry123
    state_up          / state123
    mp_priya_saroj    / mp123
    district_jaunpur  / district123
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from config import DEMO_USERS_RAW

SECRET_KEY = "mplads-sih-demo-secret-key-change-in-production-2026"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 hours — long enough for a demo/judging session

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# Pre-hash the demo passwords once at import time
DEMO_USERS = {
    username: {**info, "hashed_password": pwd_context.hash(info["password"])}
    for username, info in DEMO_USERS_RAW.items()
}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    scope: Optional[str] = None
    display_name: str


class CurrentUser(BaseModel):
    username: str
    role: str
    scope: Optional[str] = None
    display_name: str


def authenticate_user(username: str, password: str):
    user = DEMO_USERS.get(username)
    if not user or not pwd_context.verify(password, user["hashed_password"]):
        return None
    return user


def create_access_token(username: str, role: str, scope: Optional[str]) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": username, "role": role, "scope": scope, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme)) -> CurrentUser:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        role = payload.get("role")
        scope = payload.get("scope")
        if username is None or role is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user_record = DEMO_USERS.get(username)
    display_name = user_record["display_name"] if user_record else username
    return CurrentUser(username=username, role=role, scope=scope, display_name=display_name)


def require_roles(*roles: str):
    """Dependency factory: restrict an endpoint to specific roles."""
    def _dep(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"role '{user.role}' is not permitted to access this endpoint "
                       f"(requires one of {sorted(roles)})",
            )
        return user
    return _dep
