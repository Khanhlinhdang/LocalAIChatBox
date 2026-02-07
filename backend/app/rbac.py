"""
RBAC - Role-Based Access Control System
Provides fine-grained permission management with roles, permissions,
and per-document access control.
"""

from enum import Enum
from typing import List, Optional, Set
from functools import wraps
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth import get_current_user
from app.models import User


# ==================== PERMISSION DEFINITIONS ====================

class Permission(str, Enum):
    # Document permissions
    DOCUMENT_READ = "document:read"
    DOCUMENT_WRITE = "document:write"
    DOCUMENT_DELETE = "document:delete"
    DOCUMENT_SHARE = "document:share"
    DOCUMENT_MANAGE_PERMISSIONS = "document:manage_permissions"

    # Chat permissions
    CHAT_USE = "chat:use"
    CHAT_EXPORT = "chat:export"

    # Research permissions
    RESEARCH_USE = "research:use"
    RESEARCH_EXPORT = "research:export"

    # Knowledge Graph
    KG_VIEW = "kg:view"
    KG_REBUILD = "kg:rebuild"

    # Admin permissions
    ADMIN_VIEW_STATS = "admin:view_stats"
    ADMIN_MANAGE_USERS = "admin:manage_users"
    ADMIN_MANAGE_ROLES = "admin:manage_roles"
    ADMIN_MANAGE_SETTINGS = "admin:manage_settings"
    ADMIN_VIEW_AUDIT = "admin:view_audit"
    ADMIN_COMPLIANCE = "admin:compliance"

    # Tenant management
    TENANT_MANAGE = "tenant:manage"

    # Analytics
    ANALYTICS_VIEW = "analytics:view"
    ANALYTICS_EXPORT = "analytics:export"

    # Folder / Tag management
    FOLDER_MANAGE = "folder:manage"
    TAG_MANAGE = "tag:manage"


# ==================== DEFAULT ROLE DEFINITIONS ====================

DEFAULT_ROLES = {
    "viewer": {
        "description": "Can view documents and chat history only",
        "permissions": [
            Permission.DOCUMENT_READ,
            Permission.CHAT_USE,
            Permission.KG_VIEW,
            Permission.ANALYTICS_VIEW,
        ],
    },
    "editor": {
        "description": "Can upload, edit, and manage documents",
        "permissions": [
            Permission.DOCUMENT_READ,
            Permission.DOCUMENT_WRITE,
            Permission.DOCUMENT_DELETE,
            Permission.DOCUMENT_SHARE,
            Permission.CHAT_USE,
            Permission.CHAT_EXPORT,
            Permission.RESEARCH_USE,
            Permission.RESEARCH_EXPORT,
            Permission.KG_VIEW,
            Permission.ANALYTICS_VIEW,
            Permission.ANALYTICS_EXPORT,
            Permission.FOLDER_MANAGE,
            Permission.TAG_MANAGE,
        ],
    },
    "manager": {
        "description": "Can manage users and view audit logs",
        "permissions": [
            Permission.DOCUMENT_READ,
            Permission.DOCUMENT_WRITE,
            Permission.DOCUMENT_DELETE,
            Permission.DOCUMENT_SHARE,
            Permission.DOCUMENT_MANAGE_PERMISSIONS,
            Permission.CHAT_USE,
            Permission.CHAT_EXPORT,
            Permission.RESEARCH_USE,
            Permission.RESEARCH_EXPORT,
            Permission.KG_VIEW,
            Permission.KG_REBUILD,
            Permission.ADMIN_VIEW_STATS,
            Permission.ADMIN_MANAGE_USERS,
            Permission.ADMIN_VIEW_AUDIT,
            Permission.ANALYTICS_VIEW,
            Permission.ANALYTICS_EXPORT,
            Permission.FOLDER_MANAGE,
            Permission.TAG_MANAGE,
        ],
    },
    "admin": {
        "description": "Full system access",
        "permissions": [p.value for p in Permission],
    },
}


# ==================== RBAC SERVICE ====================

class RBACService:
    """Service class for RBAC operations"""

    @staticmethod
    def get_user_permissions(db: Session, user: User) -> Set[str]:
        """Get all permissions for a user based on their roles"""
        from app.models import UserRole, Role, RolePermission

        if user.is_admin:
            return {p.value for p in Permission}

        permissions = set()
        user_roles = db.query(UserRole).filter(UserRole.user_id == user.id).all()
        for ur in user_roles:
            role = db.query(Role).filter(Role.id == ur.role_id).first()
            if role and role.is_active:
                role_perms = db.query(RolePermission).filter(
                    RolePermission.role_id == role.id
                ).all()
                for rp in role_perms:
                    permissions.add(rp.permission)

        # If no roles assigned, give default editor permissions
        if not permissions and not user_roles:
            permissions = {p.value if isinstance(p, Permission) else p
                          for p in DEFAULT_ROLES["editor"]["permissions"]}

        return permissions

    @staticmethod
    def check_permission(db: Session, user: User, permission: str) -> bool:
        """Check if a user has a specific permission"""
        permissions = RBACService.get_user_permissions(db, user)
        return permission in permissions

    @staticmethod
    def check_document_access(db: Session, user: User, document_id: int, required_level: str = "read") -> bool:
        """Check if a user has access to a specific document"""
        from app.models import DocumentPermission, Document as DBDocument

        if user.is_admin:
            return True

        doc = db.query(DBDocument).filter(DBDocument.id == document_id).first()
        if not doc:
            return False

        # Owner always has full access
        if doc.uploaded_by == user.id:
            return True

        # Check per-document permissions
        doc_perm = db.query(DocumentPermission).filter(
            DocumentPermission.document_id == document_id,
            DocumentPermission.user_id == user.id
        ).first()

        if doc_perm:
            level_hierarchy = {"read": 0, "write": 1, "manage": 2}
            req_level = level_hierarchy.get(required_level, 0)
            user_level = level_hierarchy.get(doc_perm.access_level, 0)
            return user_level >= req_level

        # Check if document has no explicit permissions (public within tenant)
        has_any_perms = db.query(DocumentPermission).filter(
            DocumentPermission.document_id == document_id
        ).count()

        if has_any_perms == 0:
            # No explicit perms means accessible to all authenticated users
            return True

        return False

    @staticmethod
    def initialize_default_roles(db: Session):
        """Create default roles if they don't exist"""
        from app.models import Role, RolePermission

        for role_name, role_def in DEFAULT_ROLES.items():
            existing = db.query(Role).filter(Role.name == role_name).first()
            if not existing:
                role = Role(
                    name=role_name,
                    description=role_def["description"],
                    is_system=True,
                    is_active=True,
                )
                db.add(role)
                db.flush()

                for perm in role_def["permissions"]:
                    perm_val = perm.value if isinstance(perm, Permission) else perm
                    rp = RolePermission(role_id=role.id, permission=perm_val)
                    db.add(rp)

        db.commit()

    @staticmethod
    def assign_role_to_user(db: Session, user_id: int, role_name: str, assigned_by: int):
        """Assign a role to a user"""
        from app.models import Role, UserRole

        role = db.query(Role).filter(Role.name == role_name).first()
        if not role:
            raise ValueError(f"Role '{role_name}' not found")

        existing = db.query(UserRole).filter(
            UserRole.user_id == user_id,
            UserRole.role_id == role.id
        ).first()
        if existing:
            return existing

        user_role = UserRole(
            user_id=user_id,
            role_id=role.id,
            assigned_by=assigned_by
        )
        db.add(user_role)
        db.commit()
        return user_role


# ==================== DEPENDENCY FUNCTIONS ====================

def require_permission(permission: str):
    """FastAPI dependency that checks for a specific permission"""
    async def _check(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ) -> User:
        if not RBACService.check_permission(db, current_user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission}"
            )
        return current_user
    return _check


def require_document_access(required_level: str = "read"):
    """Factory for document access dependency — requires doc_id as path param"""
    async def _check(
        doc_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ) -> User:
        if not RBACService.check_document_access(db, current_user, doc_id, required_level):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"No {required_level} access to this document"
            )
        return current_user
    return _check
