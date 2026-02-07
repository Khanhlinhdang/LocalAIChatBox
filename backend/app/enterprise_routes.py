"""
Enterprise Routes
All Phase 4 enterprise endpoints: RBAC, Tenants, Document Permissions,
LDAP, Encryption, Compliance/GDPR.
"""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_user, get_current_admin
from app.models import (
    User, Role, RolePermission, UserRole,
    Tenant, DocumentPermission, Document, AuditLog,
)
from app.rbac import RBACService, Permission, require_permission, DEFAULT_ROLES
from app.encryption import get_encryption_service
from app.ldap_auth import get_ldap_service
from app.compliance import get_compliance_service

router = APIRouter()


# ==================== PYDANTIC SCHEMAS ====================

class RoleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    permissions: List[str] = []

class RoleUpdate(BaseModel):
    description: Optional[str] = None
    permissions: Optional[List[str]] = None
    is_active: Optional[bool] = None

class AssignRoleRequest(BaseModel):
    user_id: int
    role_name: str

class RemoveRoleRequest(BaseModel):
    user_id: int
    role_id: int

class TenantCreate(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    max_users: int = 0
    max_storage_mb: int = 0

class TenantUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    max_users: Optional[int] = None
    max_storage_mb: Optional[int] = None

class AssignTenantRequest(BaseModel):
    user_id: int
    tenant_id: int

class DocPermissionCreate(BaseModel):
    document_id: int
    user_id: int
    access_level: str = "read"  # read, write, manage

class DocPermissionUpdate(BaseModel):
    access_level: str

class AuditLogQuery(BaseModel):
    user_id: Optional[int] = None
    action: Optional[str] = None
    resource_type: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    limit: int = 100
    offset: int = 0

class GDPRExportRequest(BaseModel):
    user_id: int

class GDPRDeleteRequest(BaseModel):
    user_id: int
    delete_account: bool = False

class ComplianceReportRequest(BaseModel):
    report_type: str = "general"

class LDAPConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    server_url: Optional[str] = None
    base_dn: Optional[str] = None


# ==================== ROLE MANAGEMENT ====================

@router.get("/roles")
async def list_roles(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all roles with their permissions"""
    roles = db.query(Role).all()
    result = []
    for role in roles:
        perms = db.query(RolePermission).filter(RolePermission.role_id == role.id).all()
        result.append({
            "id": role.id,
            "name": role.name,
            "description": role.description,
            "is_system": role.is_system,
            "is_active": role.is_active,
            "created_at": role.created_at.isoformat() if role.created_at else None,
            "permissions": [p.permission for p in perms],
        })
    return {"roles": result}


@router.post("/roles")
async def create_role(
    data: RoleCreate,
    current_user: User = Depends(require_permission(Permission.ADMIN_MANAGE_ROLES)),
    db: Session = Depends(get_db)
):
    """Create a new custom role"""
    existing = db.query(Role).filter(Role.name == data.name).first()
    if existing:
        raise HTTPException(400, "Role already exists")

    role = Role(name=data.name, description=data.description, is_system=False)
    db.add(role)
    db.flush()

    for perm in data.permissions:
        rp = RolePermission(role_id=role.id, permission=perm)
        db.add(rp)

    db.commit()

    get_compliance_service().log_action(
        db, current_user.id, "role_created", "role", role.id, f"Role: {data.name}"
    )

    return {"message": "Role created", "role_id": role.id}


@router.put("/roles/{role_id}")
async def update_role(
    role_id: int,
    data: RoleUpdate,
    current_user: User = Depends(require_permission(Permission.ADMIN_MANAGE_ROLES)),
    db: Session = Depends(get_db)
):
    """Update a role's permissions or status"""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(404, "Role not found")

    if data.description is not None:
        role.description = data.description
    if data.is_active is not None:
        role.is_active = data.is_active
    if data.permissions is not None:
        db.query(RolePermission).filter(RolePermission.role_id == role.id).delete()
        for perm in data.permissions:
            rp = RolePermission(role_id=role.id, permission=perm)
            db.add(rp)

    db.commit()

    get_compliance_service().log_action(
        db, current_user.id, "role_updated", "role", role.id, f"Role: {role.name}"
    )

    return {"message": "Role updated"}


@router.delete("/roles/{role_id}")
async def delete_role(
    role_id: int,
    current_user: User = Depends(require_permission(Permission.ADMIN_MANAGE_ROLES)),
    db: Session = Depends(get_db)
):
    """Delete a custom role"""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(404, "Role not found")
    if role.is_system:
        raise HTTPException(400, "Cannot delete system role")

    db.query(UserRole).filter(UserRole.role_id == role_id).delete()
    db.query(RolePermission).filter(RolePermission.role_id == role_id).delete()
    db.delete(role)
    db.commit()

    get_compliance_service().log_action(
        db, current_user.id, "role_deleted", "role", role_id, f"Role: {role.name}"
    )

    return {"message": "Role deleted"}


@router.post("/roles/assign")
async def assign_role(
    data: AssignRoleRequest,
    current_user: User = Depends(require_permission(Permission.ADMIN_MANAGE_ROLES)),
    db: Session = Depends(get_db)
):
    """Assign a role to a user"""
    try:
        RBACService.assign_role_to_user(db, data.user_id, data.role_name, current_user.id)
        get_compliance_service().log_action(
            db, current_user.id, "role_assigned", "user", data.user_id,
            f"Role: {data.role_name}"
        )
        return {"message": f"Role '{data.role_name}' assigned to user {data.user_id}"}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/roles/remove")
async def remove_role(
    data: RemoveRoleRequest,
    current_user: User = Depends(require_permission(Permission.ADMIN_MANAGE_ROLES)),
    db: Session = Depends(get_db)
):
    """Remove a role from a user"""
    ur = db.query(UserRole).filter(
        UserRole.user_id == data.user_id,
        UserRole.role_id == data.role_id
    ).first()
    if not ur:
        raise HTTPException(404, "User does not have this role")
    db.delete(ur)
    db.commit()

    get_compliance_service().log_action(
        db, current_user.id, "role_removed", "user", data.user_id,
        f"Role ID: {data.role_id}"
    )

    return {"message": "Role removed"}


@router.get("/users/{user_id}/roles")
async def get_user_roles(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get roles assigned to a user"""
    if current_user.id != user_id and not current_user.is_admin:
        if not RBACService.check_permission(db, current_user, Permission.ADMIN_MANAGE_USERS):
            raise HTTPException(403, "Permission denied")

    user_roles = db.query(UserRole).filter(UserRole.user_id == user_id).all()
    result = []
    for ur in user_roles:
        role = db.query(Role).filter(Role.id == ur.role_id).first()
        if role:
            perms = db.query(RolePermission).filter(RolePermission.role_id == role.id).all()
            result.append({
                "role_id": role.id,
                "name": role.name,
                "description": role.description,
                "permissions": [p.permission for p in perms],
                "assigned_at": ur.assigned_at.isoformat() if ur.assigned_at else None,
            })

    return {"user_id": user_id, "roles": result}


@router.get("/users/{user_id}/permissions")
async def get_user_permissions(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get effective permissions for a user"""
    if current_user.id != user_id and not current_user.is_admin:
        raise HTTPException(403, "Permission denied")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    permissions = RBACService.get_user_permissions(db, user)
    return {"user_id": user_id, "permissions": sorted(list(permissions))}


@router.get("/permissions/list")
async def list_all_permissions(current_user: User = Depends(get_current_user)):
    """List all available permissions in the system"""
    return {
        "permissions": [
            {"value": p.value, "name": p.name}
            for p in Permission
        ]
    }


# ==================== TENANT MANAGEMENT ====================

@router.get("/tenants")
async def list_tenants(
    current_user: User = Depends(require_permission(Permission.TENANT_MANAGE)),
    db: Session = Depends(get_db)
):
    """List all tenants"""
    tenants = db.query(Tenant).all()
    result = []
    for t in tenants:
        user_count = db.query(User).filter(User.tenant_id == t.id).count()
        doc_count = db.query(Document).filter(Document.tenant_id == t.id).count()
        result.append({
            "id": t.id,
            "name": t.name,
            "slug": t.slug,
            "description": t.description,
            "is_active": t.is_active,
            "max_users": t.max_users,
            "max_storage_mb": t.max_storage_mb,
            "user_count": user_count,
            "document_count": doc_count,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        })
    return {"tenants": result}


@router.post("/tenants")
async def create_tenant(
    data: TenantCreate,
    current_user: User = Depends(require_permission(Permission.TENANT_MANAGE)),
    db: Session = Depends(get_db)
):
    """Create a new tenant"""
    existing = db.query(Tenant).filter(Tenant.slug == data.slug).first()
    if existing:
        raise HTTPException(400, "Tenant slug already exists")

    tenant = Tenant(
        name=data.name,
        slug=data.slug,
        description=data.description,
        max_users=data.max_users,
        max_storage_mb=data.max_storage_mb,
    )
    db.add(tenant)
    db.commit()

    get_compliance_service().log_action(
        db, current_user.id, "tenant_created", "tenant", tenant.id, f"Tenant: {data.name}"
    )

    return {"message": "Tenant created", "tenant_id": tenant.id}


@router.put("/tenants/{tenant_id}")
async def update_tenant(
    tenant_id: int,
    data: TenantUpdate,
    current_user: User = Depends(require_permission(Permission.TENANT_MANAGE)),
    db: Session = Depends(get_db)
):
    """Update tenant settings"""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(404, "Tenant not found")

    if data.name is not None:
        tenant.name = data.name
    if data.description is not None:
        tenant.description = data.description
    if data.is_active is not None:
        tenant.is_active = data.is_active
    if data.max_users is not None:
        tenant.max_users = data.max_users
    if data.max_storage_mb is not None:
        tenant.max_storage_mb = data.max_storage_mb

    db.commit()

    get_compliance_service().log_action(
        db, current_user.id, "tenant_updated", "tenant", tenant_id
    )

    return {"message": "Tenant updated"}


@router.delete("/tenants/{tenant_id}")
async def delete_tenant(
    tenant_id: int,
    current_user: User = Depends(require_permission(Permission.TENANT_MANAGE)),
    db: Session = Depends(get_db)
):
    """Delete a tenant (only if empty)"""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(404, "Tenant not found")

    user_count = db.query(User).filter(User.tenant_id == tenant_id).count()
    if user_count > 0:
        raise HTTPException(400, f"Cannot delete tenant with {user_count} users")

    db.delete(tenant)
    db.commit()

    get_compliance_service().log_action(
        db, current_user.id, "tenant_deleted", "tenant", tenant_id
    )

    return {"message": "Tenant deleted"}


@router.post("/tenants/assign-user")
async def assign_user_to_tenant(
    data: AssignTenantRequest,
    current_user: User = Depends(require_permission(Permission.TENANT_MANAGE)),
    db: Session = Depends(get_db)
):
    """Assign a user to a tenant"""
    user = db.query(User).filter(User.id == data.user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    tenant = db.query(Tenant).filter(Tenant.id == data.tenant_id).first()
    if not tenant:
        raise HTTPException(404, "Tenant not found")

    if tenant.max_users > 0:
        current_count = db.query(User).filter(User.tenant_id == tenant.id).count()
        if current_count >= tenant.max_users:
            raise HTTPException(400, "Tenant has reached maximum user limit")

    user.tenant_id = data.tenant_id
    db.commit()

    get_compliance_service().log_action(
        db, current_user.id, "user_assigned_tenant", "user", data.user_id,
        f"Tenant: {tenant.name}"
    )

    return {"message": f"User assigned to tenant '{tenant.name}'"}


# ==================== DOCUMENT PERMISSIONS ====================

@router.get("/documents/{doc_id}/permissions")
async def get_document_permissions(
    doc_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get permissions for a document"""
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")

    # Must be owner, admin, or have manage permission
    if doc.uploaded_by != current_user.id and not current_user.is_admin:
        if not RBACService.check_document_access(db, current_user, doc_id, "manage"):
            raise HTTPException(403, "Permission denied")

    perms = db.query(DocumentPermission).filter(
        DocumentPermission.document_id == doc_id
    ).all()

    return {
        "document_id": doc_id,
        "owner_id": doc.uploaded_by,
        "permissions": [
            {
                "id": p.id,
                "user_id": p.user_id,
                "role_id": p.role_id,
                "access_level": p.access_level,
                "granted_by": p.granted_by,
                "granted_at": p.granted_at.isoformat() if p.granted_at else None,
            }
            for p in perms
        ],
    }


@router.post("/documents/permissions")
async def grant_document_permission(
    data: DocPermissionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Grant permission on a document to a user"""
    doc = db.query(Document).filter(Document.id == data.document_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")

    # Only owner, admin, or managers can grant permissions
    if doc.uploaded_by != current_user.id and not current_user.is_admin:
        if not RBACService.check_document_access(db, current_user, data.document_id, "manage"):
            raise HTTPException(403, "Permission denied")

    if data.access_level not in ("read", "write", "manage"):
        raise HTTPException(400, "Invalid access level. Use: read, write, manage")

    # Check if permission already exists
    existing = db.query(DocumentPermission).filter(
        DocumentPermission.document_id == data.document_id,
        DocumentPermission.user_id == data.user_id,
    ).first()

    if existing:
        existing.access_level = data.access_level
    else:
        perm = DocumentPermission(
            document_id=data.document_id,
            user_id=data.user_id,
            access_level=data.access_level,
            granted_by=current_user.id,
        )
        db.add(perm)

    db.commit()

    get_compliance_service().log_action(
        db, current_user.id, "document_permission_granted", "document",
        data.document_id, f"User {data.user_id}: {data.access_level}"
    )

    return {"message": "Permission granted"}


@router.delete("/documents/permissions/{perm_id}")
async def revoke_document_permission(
    perm_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Revoke a document permission"""
    perm = db.query(DocumentPermission).filter(DocumentPermission.id == perm_id).first()
    if not perm:
        raise HTTPException(404, "Permission not found")

    doc = db.query(Document).filter(Document.id == perm.document_id).first()
    if doc.uploaded_by != current_user.id and not current_user.is_admin:
        if not RBACService.check_document_access(db, current_user, perm.document_id, "manage"):
            raise HTTPException(403, "Permission denied")

    db.delete(perm)
    db.commit()

    get_compliance_service().log_action(
        db, current_user.id, "document_permission_revoked", "document",
        perm.document_id, f"Permission ID: {perm_id}"
    )

    return {"message": "Permission revoked"}


# ==================== LDAP / SSO ====================

@router.get("/ldap/status")
async def ldap_status(
    current_user: User = Depends(require_permission(Permission.ADMIN_MANAGE_SETTINGS)),
    db: Session = Depends(get_db)
):
    """Get LDAP connection status"""
    ldap_svc = get_ldap_service()
    return ldap_svc.test_connection()


@router.get("/ldap/config")
async def ldap_config(
    current_user: User = Depends(require_permission(Permission.ADMIN_MANAGE_SETTINGS)),
):
    """Get LDAP configuration (without secrets)"""
    ldap_svc = get_ldap_service()
    return ldap_svc.get_config_summary()


# ==================== ENCRYPTION ====================

@router.get("/encryption/status")
async def encryption_status(
    current_user: User = Depends(require_permission(Permission.ADMIN_MANAGE_SETTINGS)),
):
    """Get encryption at rest status"""
    enc_svc = get_encryption_service()
    return enc_svc.get_status()


@router.post("/encryption/generate-key")
async def generate_encryption_key(
    current_user: User = Depends(require_permission(Permission.ADMIN_MANAGE_SETTINGS)),
    db: Session = Depends(get_db)
):
    """Generate a new encryption key (for reference — must be set via env var)"""
    from app.encryption import EncryptionService
    key = EncryptionService.generate_key()

    get_compliance_service().log_action(
        db, current_user.id, "encryption_key_generated", "system"
    )

    return {
        "key": key,
        "message": "Set this as ENCRYPTION_KEY environment variable in docker-compose.yml"
    }


# ==================== COMPLIANCE / GDPR ====================

@router.get("/audit-logs")
async def query_audit_logs(
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(require_permission(Permission.ADMIN_VIEW_AUDIT)),
    db: Session = Depends(get_db)
):
    """Query audit logs with filters"""
    start_dt = datetime.fromisoformat(start_date) if start_date else None
    end_dt = datetime.fromisoformat(end_date) if end_date else None

    return get_compliance_service().get_audit_logs(
        db, user_id=user_id, action=action, resource_type=resource_type,
        start_date=start_dt, end_date=end_dt, limit=limit, offset=offset
    )


@router.post("/gdpr/export")
async def gdpr_export_user_data(
    data: GDPRExportRequest,
    current_user: User = Depends(require_permission(Permission.ADMIN_COMPLIANCE)),
    db: Session = Depends(get_db)
):
    """Export all data for a user (GDPR Article 15)"""
    result = get_compliance_service().export_user_data(db, data.user_id)

    get_compliance_service().log_action(
        db, current_user.id, "gdpr_data_export", "user", data.user_id,
        "GDPR Right of Access - Data Exported"
    )

    return result


@router.post("/gdpr/delete")
async def gdpr_delete_user_data(
    data: GDPRDeleteRequest,
    current_user: User = Depends(require_permission(Permission.ADMIN_COMPLIANCE)),
    db: Session = Depends(get_db)
):
    """Delete all data for a user (GDPR Article 17)"""
    if data.user_id == current_user.id:
        raise HTTPException(400, "Cannot delete your own data while logged in")

    result = get_compliance_service().delete_user_data(
        db, data.user_id, data.delete_account
    )

    get_compliance_service().log_action(
        db, current_user.id, "gdpr_data_deletion", "user", data.user_id,
        f"GDPR Right to Erasure - Account deleted: {data.delete_account}"
    )

    return result


@router.get("/compliance/report")
async def compliance_report(
    report_type: str = "general",
    current_user: User = Depends(require_permission(Permission.ADMIN_COMPLIANCE)),
    db: Session = Depends(get_db)
):
    """Generate compliance report"""
    report = get_compliance_service().generate_compliance_report(db, report_type)

    get_compliance_service().log_action(
        db, current_user.id, "compliance_report_generated", "system",
        details=f"Report type: {report_type}"
    )

    return report


@router.get("/compliance/audit-csv")
async def export_audit_csv(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: User = Depends(require_permission(Permission.ADMIN_COMPLIANCE)),
    db: Session = Depends(get_db)
):
    """Export audit logs as CSV"""
    from fastapi.responses import Response

    start_dt = datetime.fromisoformat(start_date) if start_date else None
    end_dt = datetime.fromisoformat(end_date) if end_date else None

    csv_content = get_compliance_service().export_audit_csv(db, start_dt, end_dt)

    get_compliance_service().log_action(
        db, current_user.id, "audit_csv_exported", "system"
    )

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_logs.csv"}
    )


# ==================== ENTERPRISE DASHBOARD ====================

@router.get("/dashboard")
async def enterprise_dashboard(
    current_user: User = Depends(require_permission(Permission.ADMIN_VIEW_STATS)),
    db: Session = Depends(get_db)
):
    """Enterprise dashboard with consolidated stats"""
    from sqlalchemy import func

    total_users = db.query(func.count(User.id)).scalar()
    total_roles = db.query(func.count(Role.id)).scalar()
    total_tenants = db.query(func.count(Tenant.id)).scalar()
    total_docs = db.query(func.count(Document.id)).scalar()
    total_permissions = db.query(func.count(DocumentPermission.id)).scalar()

    recent_audits = db.query(AuditLog).order_by(
        AuditLog.created_at.desc()
    ).limit(10).all()

    enc_svc = get_encryption_service()
    ldap_svc = get_ldap_service()

    return {
        "stats": {
            "total_users": total_users,
            "total_roles": total_roles,
            "total_tenants": total_tenants,
            "total_documents": total_docs,
            "total_permissions": total_permissions,
        },
        "encryption": enc_svc.get_status(),
        "ldap": ldap_svc.get_config_summary(),
        "recent_activity": [
            {
                "id": a.id,
                "user_id": a.user_id,
                "action": a.action,
                "resource_type": a.resource_type,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in recent_audits
        ],
    }
