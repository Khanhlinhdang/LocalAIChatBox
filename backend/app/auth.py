from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
import os
import logging

logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

security = HTTPBearer()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password using bcrypt directly (compatible with bcrypt>=4.0)."""
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )


def get_password_hash(password: str) -> str:
    """Hash password using bcrypt directly (compatible with bcrypt>=4.0)."""
    return bcrypt.hashpw(
        password.encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    token = credentials.credentials
    payload = decode_token(token)

    username: str = payload.get("sub")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )

    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )

    return user


async def get_current_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user


def authenticate_with_ldap(username: str, password: str, db: Session) -> Optional[User]:
    """
    Try LDAP authentication. If successful, auto-create or update local user.
    Returns User on success, None if LDAP unavailable or auth fails.
    """
    try:
        from app.ldap_auth import get_ldap_service
        from app.rbac import RBACService

        ldap_svc = get_ldap_service()
        if not ldap_svc.available:
            return None

        ldap_info = ldap_svc.authenticate(username, password)
        if not ldap_info:
            return None

        # Find or create local user
        user = db.query(User).filter(User.username == username).first()
        if user:
            # Update existing user with LDAP info
            user.email = ldap_info.get("email") or user.email
            user.full_name = ldap_info.get("full_name") or user.full_name
            user.ldap_dn = ldap_info.get("dn")
            user.auth_provider = "ldap"
            if ldap_info.get("is_admin"):
                user.is_admin = True
            db.commit()
        else:
            if not ldap_svc.config.auto_create_users:
                logger.info(f"LDAP user {username} not auto-created (disabled)")
                return None

            # Auto-create user from LDAP
            user = User(
                username=username,
                email=ldap_info.get("email") or f"{username}@ldap.local",
                full_name=ldap_info.get("full_name") or username,
                hashed_password=get_password_hash("ldap-managed-no-local-password"),
                is_admin=ldap_info.get("is_admin", False),
                auth_provider="ldap",
                ldap_dn=ldap_info.get("dn"),
            )
            db.add(user)
            db.commit()
            db.refresh(user)

            # Assign default role
            default_role = ldap_info.get("default_role", "editor")
            try:
                RBACService.assign_role_to_user(db, user.id, default_role, user.id)
            except Exception as e:
                logger.warning(f"Could not assign default role to LDAP user: {e}")

            logger.info(f"Auto-created LDAP user: {username}")

        return user

    except Exception as e:
        logger.error(f"LDAP authentication error: {e}")
        return None
