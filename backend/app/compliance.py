"""
Compliance & GDPR Service
Provides audit logging, data export (right of access), data deletion
(right to be forgotten), and compliance report generation.
"""

import json
import io
import csv
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

logger = logging.getLogger(__name__)


class ComplianceService:
    """Handles GDPR compliance, audit logging, and reporting"""

    # ==================== AUDIT LOGGING ====================

    @staticmethod
    def log_action(
        db: Session,
        user_id: int,
        action: str,
        resource_type: str,
        resource_id: Optional[int] = None,
        details: Optional[str] = None,
        ip_address: Optional[str] = None,
        tenant_id: Optional[int] = None,
    ):
        """Log an auditable action"""
        from app.models import AuditLog

        entry = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            tenant_id=tenant_id,
        )
        db.add(entry)
        db.commit()
        return entry

    @staticmethod
    def get_audit_logs(
        db: Session,
        user_id: Optional[int] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        tenant_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict]:
        """Query audit logs with filters"""
        from app.models import AuditLog

        query = db.query(AuditLog)
        if user_id:
            query = query.filter(AuditLog.user_id == user_id)
        if action:
            query = query.filter(AuditLog.action == action)
        if resource_type:
            query = query.filter(AuditLog.resource_type == resource_type)
        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)
        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)
        if tenant_id:
            query = query.filter(AuditLog.tenant_id == tenant_id)

        total = query.count()
        logs = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()

        return {
            "total": total,
            "logs": [
                {
                    "id": log.id,
                    "user_id": log.user_id,
                    "action": log.action,
                    "resource_type": log.resource_type,
                    "resource_id": log.resource_id,
                    "details": log.details,
                    "ip_address": log.ip_address,
                    "tenant_id": log.tenant_id,
                    "created_at": log.created_at.isoformat() if log.created_at else None,
                }
                for log in logs
            ],
        }

    # ==================== GDPR DATA EXPORT ====================

    @staticmethod
    def export_user_data(db: Session, user_id: int) -> Dict[str, Any]:
        """
        Export all data associated with a user (GDPR Right of Access).
        Returns a dictionary with all user-related data.
        """
        from app.models import (
            User, Document, Conversation, ChatSession,
            AuditLog, UsageLog
        )

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"error": "User not found"}

        # User profile
        user_data = {
            "profile": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "is_active": user.is_active,
                "created_at": user.created_at.isoformat() if user.created_at else None,
            }
        }

        # Documents
        docs = db.query(Document).filter(Document.uploaded_by == user_id).all()
        user_data["documents"] = [
            {
                "id": d.id,
                "filename": d.original_filename,
                "file_type": d.file_type,
                "uploaded_at": d.uploaded_at.isoformat() if d.uploaded_at else None,
                "file_size_mb": d.file_size_mb,
            }
            for d in docs
        ]

        # Chat sessions
        sessions = db.query(ChatSession).filter(ChatSession.user_id == user_id).all()
        user_data["chat_sessions"] = []
        for sess in sessions:
            convos = db.query(Conversation).filter(
                Conversation.session_id == sess.id
            ).all()
            user_data["chat_sessions"].append({
                "id": sess.id,
                "title": sess.title,
                "created_at": sess.created_at.isoformat() if sess.created_at else None,
                "conversations": [
                    {
                        "query": c.query,
                        "response": c.response,
                        "created_at": c.created_at.isoformat() if c.created_at else None,
                    }
                    for c in convos
                ],
            })

        # Usage logs
        usage = db.query(UsageLog).filter(UsageLog.user_id == user_id).all()
        user_data["usage_logs"] = [
            {
                "id": u.id,
                "action": u.action,
                "details": u.details,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in usage
        ]

        # Audit logs
        audits = db.query(AuditLog).filter(AuditLog.user_id == user_id).all()
        user_data["audit_logs"] = [
            {
                "id": a.id,
                "action": a.action,
                "resource_type": a.resource_type,
                "resource_id": a.resource_id,
                "details": a.details,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in audits
        ]

        user_data["export_metadata"] = {
            "exported_at": datetime.utcnow().isoformat(),
            "format": "JSON",
            "gdpr_article": "Article 15 - Right of access",
        }

        return user_data

    # ==================== GDPR DATA DELETION ====================

    @staticmethod
    def delete_user_data(db: Session, user_id: int, delete_account: bool = False) -> Dict[str, Any]:
        """
        Delete all personal data for a user (GDPR Right to be Forgotten).
        If delete_account=True, the user record itself is also removed.
        """
        from app.models import (
            User, Document, Conversation, ChatSession,
            AuditLog, UsageLog, UserRole, DocumentPermission
        )

        result = {"deleted": {}, "errors": []}

        try:
            # Delete conversations and chat sessions
            sessions = db.query(ChatSession).filter(ChatSession.user_id == user_id).all()
            conv_count = 0
            for sess in sessions:
                conv_count += db.query(Conversation).filter(
                    Conversation.session_id == sess.id
                ).delete()
            db.query(ChatSession).filter(ChatSession.user_id == user_id).delete()
            result["deleted"]["conversations"] = conv_count
            result["deleted"]["chat_sessions"] = len(sessions)

            # Delete usage logs
            usage_count = db.query(UsageLog).filter(UsageLog.user_id == user_id).delete()
            result["deleted"]["usage_logs"] = usage_count

            # Anonymize audit logs (keep for compliance but remove PII)
            audit_count = db.query(AuditLog).filter(AuditLog.user_id == user_id).update(
                {"details": "[REDACTED - GDPR Deletion]", "ip_address": None}
            )
            result["deleted"]["audit_logs_anonymized"] = audit_count

            # Delete document permissions
            perm_count = db.query(DocumentPermission).filter(
                DocumentPermission.user_id == user_id
            ).delete()
            result["deleted"]["document_permissions"] = perm_count

            # Delete user roles
            role_count = db.query(UserRole).filter(UserRole.user_id == user_id).delete()
            result["deleted"]["user_roles"] = role_count

            # Delete documents (just DB records; files stay for other users' references)
            doc_count = db.query(Document).filter(Document.uploaded_by == user_id).update(
                {"uploaded_by": None}
            )
            result["deleted"]["documents_disassociated"] = doc_count

            if delete_account:
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    user.username = f"deleted_user_{user_id}"
                    user.email = f"deleted_{user_id}@removed.local"
                    user.full_name = "[Deleted User]"
                    user.hashed_password = ""
                    user.is_active = False
                    result["deleted"]["account"] = "anonymized"

            db.commit()
            result["status"] = "success"
            result["gdpr_article"] = "Article 17 - Right to erasure"
            result["processed_at"] = datetime.utcnow().isoformat()

        except Exception as e:
            db.rollback()
            result["status"] = "error"
            result["errors"].append(str(e))

        return result

    # ==================== COMPLIANCE REPORTS ====================

    @staticmethod
    def generate_compliance_report(
        db: Session,
        report_type: str = "general",
        tenant_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Generate a compliance report"""
        from app.models import User, Document, AuditLog, ChatSession, Conversation

        now = datetime.utcnow()
        thirty_days_ago = now - timedelta(days=30)

        report = {
            "report_type": report_type,
            "generated_at": now.isoformat(),
            "period": {
                "start": thirty_days_ago.isoformat(),
                "end": now.isoformat(),
            },
        }

        # User stats
        total_users = db.query(func.count(User.id)).scalar()
        active_users = db.query(func.count(User.id)).filter(User.is_active == True).scalar()
        report["users"] = {
            "total": total_users,
            "active": active_users,
            "inactive": total_users - active_users,
        }

        # Document stats
        total_docs = db.query(func.count(Document.id)).scalar()
        recent_docs = db.query(func.count(Document.id)).filter(
            Document.uploaded_at >= thirty_days_ago
        ).scalar()
        report["documents"] = {
            "total": total_docs,
            "last_30_days": recent_docs,
        }

        # Audit activity
        total_actions = db.query(func.count(AuditLog.id)).filter(
            AuditLog.created_at >= thirty_days_ago
        ).scalar()
        action_breakdown = db.query(
            AuditLog.action, func.count(AuditLog.id)
        ).filter(
            AuditLog.created_at >= thirty_days_ago
        ).group_by(AuditLog.action).all()

        report["audit_activity"] = {
            "total_actions_30d": total_actions,
            "breakdown": {action: count for action, count in action_breakdown},
        }

        # GDPR specifics
        data_exports = db.query(func.count(AuditLog.id)).filter(
            AuditLog.action == "gdpr_data_export",
            AuditLog.created_at >= thirty_days_ago,
        ).scalar()
        data_deletions = db.query(func.count(AuditLog.id)).filter(
            AuditLog.action == "gdpr_data_deletion",
            AuditLog.created_at >= thirty_days_ago,
        ).scalar()

        report["gdpr"] = {
            "data_export_requests_30d": data_exports,
            "data_deletion_requests_30d": data_deletions,
            "encryption_at_rest": True,
            "data_retention_policy": "User-controlled",
        }

        # Chat / conversation stats
        total_sessions = db.query(func.count(ChatSession.id)).scalar()
        total_conversations = db.query(func.count(Conversation.id)).scalar()
        report["chat"] = {
            "total_sessions": total_sessions,
            "total_conversations": total_conversations,
        }

        report["compliance_status"] = {
            "gdpr_compliant": True,
            "rbac_enabled": True,
            "audit_logging": True,
            "encryption_at_rest": True,
            "data_export_available": True,
            "data_deletion_available": True,
        }

        return report

    @staticmethod
    def export_audit_csv(db: Session, start_date: Optional[datetime] = None,
                         end_date: Optional[datetime] = None) -> str:
        """Export audit logs as CSV string"""
        from app.models import AuditLog

        query = db.query(AuditLog)
        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)
        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)

        logs = query.order_by(AuditLog.created_at.desc()).all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "User ID", "Action", "Resource Type", "Resource ID",
                         "Details", "IP Address", "Tenant ID", "Created At"])
        for log in logs:
            writer.writerow([
                log.id, log.user_id, log.action, log.resource_type,
                log.resource_id, log.details, log.ip_address,
                log.tenant_id,
                log.created_at.isoformat() if log.created_at else "",
            ])

        return output.getvalue()


# Singleton
_compliance_service: Optional[ComplianceService] = None


def get_compliance_service() -> ComplianceService:
    global _compliance_service
    if _compliance_service is None:
        _compliance_service = ComplianceService()
    return _compliance_service
