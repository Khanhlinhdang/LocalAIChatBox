"""
Encryption at Rest Service
Provides file-level and field-level encryption using Fernet (AES-128-CBC).
"""

import os
import base64
import hashlib
import logging
from typing import Optional
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


class EncryptionService:
    """Handles encryption and decryption of data at rest"""

    def __init__(self, encryption_key: Optional[str] = None):
        self._enabled = False
        key = encryption_key or os.getenv("ENCRYPTION_KEY", "")
        if key:
            try:
                # Derive a valid Fernet key from any string
                derived = hashlib.sha256(key.encode()).digest()
                self._fernet_key = base64.urlsafe_b64encode(derived)
                self._fernet = Fernet(self._fernet_key)
                self._enabled = True
                logger.info("Encryption service initialized successfully")
            except Exception as e:
                logger.warning(f"Encryption service disabled: {e}")
                self._fernet = None
        else:
            logger.info("ENCRYPTION_KEY not set — encryption at rest disabled")
            self._fernet = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    # ---- Field-level encryption ----

    def encrypt_text(self, plaintext: str) -> str:
        """Encrypt a string and return base64-encoded ciphertext"""
        if not self._fernet:
            return plaintext
        try:
            encrypted = self._fernet.encrypt(plaintext.encode("utf-8"))
            return encrypted.decode("utf-8")
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            return plaintext

    def decrypt_text(self, ciphertext: str) -> str:
        """Decrypt a base64-encoded ciphertext"""
        if not self._fernet:
            return ciphertext
        try:
            decrypted = self._fernet.decrypt(ciphertext.encode("utf-8"))
            return decrypted.decode("utf-8")
        except Exception as e:
            logger.error(f"Decryption failed (data may not be encrypted): {e}")
            return ciphertext

    # ---- File-level encryption ----

    def encrypt_file(self, file_path: str) -> bool:
        """Encrypt a file in place. Returns True on success."""
        if not self._fernet:
            return False
        try:
            with open(file_path, "rb") as f:
                data = f.read()
            encrypted = self._fernet.encrypt(data)
            enc_path = file_path + ".enc"
            with open(enc_path, "wb") as f:
                f.write(encrypted)
            os.replace(enc_path, file_path)
            logger.info(f"Encrypted file: {file_path}")
            return True
        except Exception as e:
            logger.error(f"File encryption failed for {file_path}: {e}")
            return False

    def decrypt_file(self, file_path: str) -> Optional[bytes]:
        """Decrypt a file and return its contents as bytes."""
        if not self._fernet:
            try:
                with open(file_path, "rb") as f:
                    return f.read()
            except Exception:
                return None
        try:
            with open(file_path, "rb") as f:
                data = f.read()
            return self._fernet.decrypt(data)
        except Exception:
            # Might not be encrypted – return raw
            try:
                with open(file_path, "rb") as f:
                    return f.read()
            except Exception:
                return None

    def decrypt_file_to_path(self, encrypted_path: str, output_path: str) -> bool:
        """Decrypt a file and write to output path."""
        data = self.decrypt_file(encrypted_path)
        if data is None:
            return False
        try:
            with open(output_path, "wb") as f:
                f.write(data)
            return True
        except Exception as e:
            logger.error(f"Failed to write decrypted file: {e}")
            return False

    # ---- Key management helpers ----

    @staticmethod
    def generate_key() -> str:
        """Generate a new random encryption key"""
        return Fernet.generate_key().decode("utf-8")

    def get_status(self) -> dict:
        """Return encryption service status"""
        return {
            "enabled": self._enabled,
            "algorithm": "Fernet (AES-128-CBC + HMAC-SHA256)" if self._enabled else None,
            "key_configured": self._fernet is not None,
        }


# Singleton instance
_encryption_service: Optional[EncryptionService] = None


def get_encryption_service() -> EncryptionService:
    """Get or create the singleton encryption service"""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service
