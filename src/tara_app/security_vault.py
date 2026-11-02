"""Secure credential and API key vault for TARA-App.

Conforms to Directive Section 2 (Secure API key storage) and Section 7 (Security and Permission System).
On Windows, uses Windows DPAPI (Data Protection API via crypt32.dll) to encrypt
secrets with the user's logon security token. Never logs plain-text credentials.
"""
from __future__ import annotations

import base64
import ctypes
import json
import os
import sys
from pathlib import Path
from typing import Any

if sys.platform == "win32":
    from ctypes import wintypes

    class _DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _dpapi_protect(data: bytes, description: str = "TARA Secret") -> bytes:
    if sys.platform != "win32":
        # Fallback for non-Windows test environments
        return b"ENC:" + base64.b64encode(data)
    in_blob = _DATA_BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data), ctypes.POINTER(ctypes.c_byte)))
    out_blob = _DATA_BLOB()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    if not crypt32.CryptProtectData(ctypes.byref(in_blob), description, None, None, None, 0, ctypes.byref(out_blob)):
        raise RuntimeError("Windows DPAPI encryption failed")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)


def _dpapi_unprotect(data: bytes) -> bytes:
    if sys.platform != "win32":
        if data.startswith(b"ENC:"):
            return base64.b64decode(data[4:])
        return data
    in_blob = _DATA_BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data), ctypes.POINTER(ctypes.c_byte)))
    out_blob = _DATA_BLOB()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    if not crypt32.CryptUnprotectData(ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)):
        raise RuntimeError("Windows DPAPI decryption failed")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)


def _default_vault_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        base = Path(local_app_data) / "TARA-App"
    else:
        base = Path.home() / ".tara"
    base.mkdir(parents=True, exist_ok=True)
    return base / "vault.bin"


class SecurityVault:
    """Encrypted key-value store using Windows DPAPI."""

    def __init__(self, vault_path: str | Path | None = None) -> None:
        self.path = Path(vault_path).resolve() if vault_path else _default_vault_path()

    def _read_vault(self) -> dict[str, str]:
        if not self.path.is_file():
            return {}
        try:
            raw = self.path.read_bytes()
            if not raw:
                return {}
            decrypted = _dpapi_unprotect(raw)
            return json.loads(decrypted.decode("utf-8"))
        except Exception:
            return {}

    def _write_vault(self, data: dict[str, str]) -> None:
        serialized = json.dumps(data, ensure_ascii=False).encode("utf-8")
        encrypted = _dpapi_protect(serialized, description="TARA Security Vault")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write
        temp_path = self.path.with_suffix(".tmp")
        temp_path.write_bytes(encrypted)
        temp_path.replace(self.path)

    def set_secret(self, key: str, value: str) -> None:
        if not isinstance(key, str) or not key.strip() or len(key) > 128:
            raise ValueError("Secret key must be a non-empty string under 128 characters")
        if not isinstance(value, str) or len(value) > 8192:
            raise ValueError("Secret value must be a string under 8192 characters")
        vault = self._read_vault()
        vault[key.strip()] = value.strip()
        self._write_vault(vault)

    def get_secret(self, key: str) -> str | None:
        if not isinstance(key, str) or not key.strip():
            return None
        vault = self._read_vault()
        return vault.get(key.strip())

    def delete_secret(self, key: str) -> bool:
        vault = self._read_vault()
        if key.strip() in vault:
            del vault[key.strip()]
            self._write_vault(vault)
            return True
        return False

    def list_keys(self) -> list[str]:
        vault = self._read_vault()
        return sorted(vault.keys())

    def get_masked_secrets(self) -> dict[str, str]:
        """Return secret names with masked values (never plaintext)."""
        vault = self._read_vault()
        masked = {}
        for k, v in vault.items():
            if len(v) <= 8:
                masked[k] = "••••••••"
            else:
                masked[k] = v[:3] + "••••••••" + v[-3:]
        return masked


__all__ = ["SecurityVault"]
