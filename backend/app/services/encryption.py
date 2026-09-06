from __future__ import annotations

import json
import logging
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import JSON, TypeDecorator

from app.config import get_settings

log = logging.getLogger(__name__)


class _Cipher:
    _fernet: Fernet | None = None

    @classmethod
    def get(cls) -> Fernet | None:
        if cls._fernet is None:
            key = get_settings().fernet_key.encode() if get_settings().fernet_key else b""
            if not key:
                log.warning("FERNET_KEY is empty; history will be stored unencrypted.")
                return None
            cls._fernet = Fernet(key)
        return cls._fernet


def encrypt_dict(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if payload is None:
        return None
    f = _Cipher.get()
    if f is None:
        return payload
    token = f.encrypt(json.dumps(payload, ensure_ascii=False).encode("utf-8")).decode("ascii")
    return {"_enc": token}


def decrypt_dict(stored: dict[str, Any] | None) -> dict[str, Any] | None:
    if stored is None:
        return None
    if "_enc" not in stored:
        return stored
    f = _Cipher.get()
    if f is None:
        return None
    try:
        raw = f.decrypt(stored["_enc"].encode("ascii"))
    except InvalidToken:
        log.error("Failed to decrypt history: invalid token.")
        return None
    return json.loads(raw.decode("utf-8"))


class EncryptedJSON(TypeDecorator):
    """
    Cross-dialect JSON column that transparently Fernet-encrypts the payload
    at rest. Stored shape is ``{"_enc": "<token>"}`` so previously-unencrypted
    rows still load. Uses SQLAlchemy generic JSON (TEXT on SQLite, JSONB on
    Postgres) so it works on both backends.
    """

    impl = JSON
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if isinstance(value, dict) and "_enc" in value:
            return value
        return encrypt_dict(value)

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        return decrypt_dict(value)


__all__ = ["EncryptedJSON", "encrypt_dict", "decrypt_dict"]
