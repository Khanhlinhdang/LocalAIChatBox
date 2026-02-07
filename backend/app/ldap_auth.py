"""
LDAP / Active Directory Authentication Service
Provides SSO via LDAP bind + search.
Falls back to local auth when LDAP is unavailable.
"""

import os
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Try import – will be available after requirements update
try:
    import ldap3
    from ldap3 import Server, Connection, ALL, SUBTREE
    LDAP_AVAILABLE = True
except ImportError:
    LDAP_AVAILABLE = False
    logger.info("ldap3 not installed – LDAP authentication disabled")


class LDAPConfig:
    """LDAP configuration from environment variables"""

    def __init__(self):
        self.enabled = os.getenv("LDAP_ENABLED", "false").lower() == "true"
        self.server_url = os.getenv("LDAP_SERVER", "ldap://localhost:389")
        self.base_dn = os.getenv("LDAP_BASE_DN", "dc=example,dc=com")
        self.bind_dn = os.getenv("LDAP_BIND_DN", "")
        self.bind_password = os.getenv("LDAP_BIND_PASSWORD", "")
        self.user_search_base = os.getenv("LDAP_USER_SEARCH_BASE", self.base_dn)
        self.user_search_filter = os.getenv(
            "LDAP_USER_SEARCH_FILTER",
            "(sAMAccountName={username})"
        )
        self.username_attribute = os.getenv("LDAP_USERNAME_ATTR", "sAMAccountName")
        self.email_attribute = os.getenv("LDAP_EMAIL_ATTR", "mail")
        self.fullname_attribute = os.getenv("LDAP_FULLNAME_ATTR", "displayName")
        self.group_search_base = os.getenv("LDAP_GROUP_SEARCH_BASE", self.base_dn)
        self.group_search_filter = os.getenv(
            "LDAP_GROUP_SEARCH_FILTER",
            "(member={user_dn})"
        )
        self.admin_group = os.getenv("LDAP_ADMIN_GROUP", "CN=Admins")
        self.use_ssl = os.getenv("LDAP_USE_SSL", "false").lower() == "true"
        self.use_tls = os.getenv("LDAP_USE_TLS", "false").lower() == "true"
        self.default_role = os.getenv("LDAP_DEFAULT_ROLE", "editor")
        self.auto_create_users = os.getenv("LDAP_AUTO_CREATE_USERS", "true").lower() == "true"


class LDAPService:
    """LDAP Authentication and user synchronization service"""

    def __init__(self, config: Optional[LDAPConfig] = None):
        self.config = config or LDAPConfig()
        self._available = LDAP_AVAILABLE and self.config.enabled

    @property
    def available(self) -> bool:
        return self._available

    def _get_server(self):
        """Create LDAP server connection"""
        if not LDAP_AVAILABLE:
            return None
        return Server(
            self.config.server_url,
            use_ssl=self.config.use_ssl,
            get_info=ALL
        )

    def _get_admin_connection(self) -> Optional['Connection']:
        """Create an admin/service account connection for searches"""
        if not self._available:
            return None
        try:
            server = self._get_server()
            conn = Connection(
                server,
                user=self.config.bind_dn,
                password=self.config.bind_password,
                auto_bind=True,
                raise_exceptions=True
            )
            if self.config.use_tls:
                conn.start_tls()
            return conn
        except Exception as e:
            logger.error(f"LDAP admin connection failed: {e}")
            return None

    def authenticate(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Authenticate a user against LDAP.
        Returns user info dict on success, None on failure.
        """
        if not self._available:
            return None

        try:
            # Step 1: Find the user DN via service account
            admin_conn = self._get_admin_connection()
            if not admin_conn:
                logger.warning("Cannot connect with service account")
                return None

            search_filter = self.config.user_search_filter.replace(
                "{username}", username
            )
            admin_conn.search(
                search_base=self.config.user_search_base,
                search_filter=search_filter,
                search_scope=SUBTREE,
                attributes=[
                    self.config.username_attribute,
                    self.config.email_attribute,
                    self.config.fullname_attribute,
                ]
            )

            if not admin_conn.entries:
                logger.info(f"LDAP user not found: {username}")
                admin_conn.unbind()
                return None

            entry = admin_conn.entries[0]
            user_dn = str(entry.entry_dn)
            admin_conn.unbind()

            # Step 2: Try to bind as the user
            server = self._get_server()
            user_conn = Connection(
                server,
                user=user_dn,
                password=password,
                auto_bind=True,
                raise_exceptions=True
            )
            user_conn.unbind()

            # Step 3: Extract user info
            user_info = {
                "username": str(getattr(entry, self.config.username_attribute, username)),
                "email": str(getattr(entry, self.config.email_attribute, "")),
                "full_name": str(getattr(entry, self.config.fullname_attribute, "")),
                "dn": user_dn,
                "ldap_authenticated": True,
            }

            # Step 4: Check group membership for admin
            user_info["is_admin"] = self._check_admin_group(user_dn)
            user_info["default_role"] = self.config.default_role

            return user_info

        except Exception as e:
            logger.error(f"LDAP authentication failed for {username}: {e}")
            return None

    def _check_admin_group(self, user_dn: str) -> bool:
        """Check if user is a member of the admin group"""
        try:
            admin_conn = self._get_admin_connection()
            if not admin_conn:
                return False

            group_filter = self.config.group_search_filter.replace(
                "{user_dn}", user_dn
            )
            admin_conn.search(
                search_base=self.config.group_search_base,
                search_filter=group_filter,
                search_scope=SUBTREE,
                attributes=["cn"]
            )

            for entry in admin_conn.entries:
                if self.config.admin_group.lower() in str(entry.entry_dn).lower():
                    admin_conn.unbind()
                    return True

            admin_conn.unbind()
            return False
        except Exception:
            return False

    def test_connection(self) -> Dict[str, Any]:
        """Test LDAP connection and return status"""
        if not LDAP_AVAILABLE:
            return {
                "status": "unavailable",
                "message": "ldap3 library not installed",
                "enabled": False,
            }

        if not self.config.enabled:
            return {
                "status": "disabled",
                "message": "LDAP authentication is disabled",
                "enabled": False,
            }

        try:
            conn = self._get_admin_connection()
            if conn:
                info = {
                    "status": "connected",
                    "message": "LDAP connection successful",
                    "enabled": True,
                    "server": self.config.server_url,
                    "base_dn": self.config.base_dn,
                    "ssl": self.config.use_ssl,
                    "tls": self.config.use_tls,
                }
                conn.unbind()
                return info
            return {
                "status": "error",
                "message": "Could not establish LDAP connection",
                "enabled": True,
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "enabled": True,
            }

    def get_config_summary(self) -> Dict[str, Any]:
        """Return config without sensitive data"""
        return {
            "enabled": self.config.enabled,
            "server_url": self.config.server_url,
            "base_dn": self.config.base_dn,
            "user_search_base": self.config.user_search_base,
            "use_ssl": self.config.use_ssl,
            "use_tls": self.config.use_tls,
            "auto_create_users": self.config.auto_create_users,
            "default_role": self.config.default_role,
            "ldap3_installed": LDAP_AVAILABLE,
        }


# Singleton
_ldap_service: Optional[LDAPService] = None


def get_ldap_service() -> LDAPService:
    global _ldap_service
    if _ldap_service is None:
        _ldap_service = LDAPService()
    return _ldap_service
