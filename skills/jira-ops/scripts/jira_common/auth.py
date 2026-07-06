"""PAT storage/retrieval across backends.

Backends, in priority order (resolved by ``AuthConfig.type == 'auto'``):
1. ``keyring`` system store (if importable and functional)
2. Encrypted local file:
   - Windows: DPAPI (CryptProtectData) via ctypes, user-scoped
   - POSIX: a 0600 file (documented as obfuscated, not strongly encrypted)

Secrets are never printed. The token file lives under the config dir, not the repo.
"""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Optional

from . import paths
from .config import Profile
from .errors import JiraOpsError

_KEYRING_SERVICE = "jira-ops"


# --------------------------------------------------------------------------- #
# keyring backend
# --------------------------------------------------------------------------- #
def _try_import_keyring():
    try:
        import keyring  # type: ignore

        # Reject the fail/null backend which silently drops secrets.
        backend = keyring.get_keyring().__class__.__name__.lower()
        if "fail" in backend or "null" in backend:
            return None
        return keyring
    except Exception:
        return None


def _keyring_set(target: str, token: str) -> bool:
    kr = _try_import_keyring()
    if kr is None:
        return False
    try:
        kr.set_password(_KEYRING_SERVICE, target, token)
        return True
    except Exception:
        return False


def _keyring_get(target: str) -> Optional[str]:
    kr = _try_import_keyring()
    if kr is None:
        return None
    try:
        return kr.get_password(_KEYRING_SERVICE, target)
    except Exception:
        return None


def _keyring_delete(target: str) -> bool:
    kr = _try_import_keyring()
    if kr is None:
        return False
    try:
        kr.delete_password(_KEYRING_SERVICE, target)
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# Windows DPAPI (ctypes, no external dependency)
# --------------------------------------------------------------------------- #
def _dpapi_available() -> bool:
    return os.name == "nt"


def _dpapi_protect(data: bytes) -> bytes:
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    def _blob(raw: bytes) -> DATA_BLOB:
        buf = ctypes.create_string_buffer(raw, len(raw))
        return DATA_BLOB(len(raw), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))

    in_blob = _blob(data)
    out_blob = DATA_BLOB()
    crypt32 = ctypes.windll.crypt32
    if not crypt32.CryptProtectData(
        ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)
    ):
        raise JiraOpsError("config", "DPAPI CryptProtectData failed.")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)


def _dpapi_unprotect(data: bytes) -> bytes:
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    def _blob(raw: bytes) -> DATA_BLOB:
        buf = ctypes.create_string_buffer(raw, len(raw))
        return DATA_BLOB(len(raw), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))

    in_blob = _blob(data)
    out_blob = DATA_BLOB()
    crypt32 = ctypes.windll.crypt32
    if not crypt32.CryptUnprotectData(
        ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)
    ):
        raise JiraOpsError("auth", "DPAPI CryptUnprotectData failed (token corrupt?).")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)


# --------------------------------------------------------------------------- #
# Encrypted-file backend
# --------------------------------------------------------------------------- #
def _token_file(profile: Profile) -> Path:
    return paths.resolve_relative(profile.auth.fallback_encrypted_path)


def _file_set(profile: Profile, token: str) -> None:
    paths.ensure_config_dir()
    path = _token_file(profile)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = token.encode("utf-8")
    if _dpapi_available():
        payload = b"DPAPI:" + base64.b64encode(_dpapi_protect(raw))
    else:
        # Obfuscation only; rely on 0600 perms. Documented in references/security.md.
        payload = b"PLAIN:" + base64.b64encode(raw)
    path.write_bytes(payload)
    if os.name != "nt":
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass


def _file_get(profile: Profile) -> Optional[str]:
    path = _token_file(profile)
    if not path.is_file():
        return None
    payload = path.read_bytes()
    if payload.startswith(b"DPAPI:"):
        if not _dpapi_available():
            raise JiraOpsError(
                "auth", "Token was DPAPI-encrypted on Windows; cannot read here."
            )
        return _dpapi_unprotect(base64.b64decode(payload[len(b"DPAPI:") :])).decode("utf-8")
    if payload.startswith(b"PLAIN:"):
        return base64.b64decode(payload[len(b"PLAIN:") :]).decode("utf-8")
    # Legacy/raw content.
    return payload.decode("utf-8").strip()


def _file_delete(profile: Profile) -> bool:
    path = _token_file(profile)
    if path.is_file():
        path.unlink()
        return True
    return False


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def describe_backend(profile: Profile) -> str:
    """Human-readable name of the backend that would be used for this profile."""
    t = profile.auth.type
    if t == "system-keyring":
        return "system keyring"
    if t == "encrypted-file":
        return "DPAPI-encrypted file" if _dpapi_available() else "local file (0600)"
    # auto
    if _try_import_keyring() is not None:
        return "system keyring"
    return "DPAPI-encrypted file" if _dpapi_available() else "local file (0600)"


def store_token(profile: Profile, token: str) -> str:
    """Persist the PAT. Returns the backend name used."""
    if not token or not token.strip():
        raise JiraOpsError("auth", "Empty token provided.")
    token = token.strip()
    t = profile.auth.type

    if t in ("auto", "system-keyring"):
        if _keyring_set(profile.auth.target, token):
            return "system keyring"
        if t == "system-keyring":
            raise JiraOpsError("auth", "keyring backend unavailable; cannot store token.")

    _file_set(profile, token)
    return describe_backend(profile)


def resolve_token(profile: Profile) -> str:
    """Retrieve the PAT, trying env override, keyring, then encrypted file."""
    # Env override for CI/automation (never logged).
    env_token = os.environ.get("JIRA_OPS_TOKEN")
    if env_token:
        return env_token.strip()

    t = profile.auth.type
    if t in ("auto", "system-keyring"):
        tok = _keyring_get(profile.auth.target)
        if tok:
            return tok
    tok = _file_get(profile)
    if tok:
        return tok
    raise JiraOpsError(
        "auth",
        f"No token stored for profile '{profile.name}'. Run 'jira auth set-token'.",
    )


def clear_token(profile: Profile) -> bool:
    """Remove any stored PAT for this profile. Returns True if something removed."""
    removed = False
    if _keyring_delete(profile.auth.target):
        removed = True
    if _file_delete(profile):
        removed = True
    return removed


def token_exists(profile: Profile) -> bool:
    """True if a PAT is already stored for this profile (ignores env override)."""
    t = profile.auth.type
    if t in ("auto", "system-keyring") and _keyring_get(profile.auth.target):
        return True
    try:
        return _file_get(profile) is not None
    except JiraOpsError:
        # A stored-but-unreadable token still counts as present.
        return True
