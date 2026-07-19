"""PEDIT EDU launcher-host boundary helpers."""

import hmac
import json
import os
import re
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


class LauncherBootstrapError(ValueError):
    pass


class LegacyDatabaseMigrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class LauncherBootstrap:
    data_dir: Path
    backend_secret: str
    session_context: dict


def parse_bootstrap_line(raw: bytes) -> LauncherBootstrap:
    if not raw or len(raw) > 65_536 or b"\n" in raw or b"\r" in raw:
        raise LauncherBootstrapError("LAUNCHER_BOOTSTRAP_INVALID_FRAME")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise LauncherBootstrapError("LAUNCHER_BOOTSTRAP_INVALID_JSON") from error
    if not isinstance(payload, dict) or set(payload) != {"dataDir", "backendSecret", "sessionContext"}:
        raise LauncherBootstrapError("LAUNCHER_BOOTSTRAP_INVALID_FIELDS")

    data_dir_raw = payload.get("dataDir")
    if not isinstance(data_dir_raw, str) or not data_dir_raw.strip():
        raise LauncherBootstrapError("LAUNCHER_DATA_DIR_INVALID")
    data_dir = Path(data_dir_raw)
    if not data_dir.is_absolute():
        raise LauncherBootstrapError("LAUNCHER_DATA_DIR_NOT_ABSOLUTE")
    data_dir = data_dir.resolve(strict=False)

    backend_secret = payload.get("backendSecret")
    if not isinstance(backend_secret, str) or re.fullmatch(r"[0-9a-f]{64}", backend_secret) is None:
        raise LauncherBootstrapError("LAUNCHER_BACKEND_SECRET_INVALID")

    session_context = validate_session_context(payload.get("sessionContext"))

    return LauncherBootstrap(data_dir, backend_secret, session_context)


def validate_session_context(session_context: object) -> dict:
    required = {"userId", "workspaceId", "roles", "scopes", "expiresAt"}
    allowed = required | {"deviceId", "dataScopeId"}
    if not isinstance(session_context, dict) or not required.issubset(session_context) or not set(session_context).issubset(allowed):
        raise LauncherBootstrapError("LAUNCHER_SESSION_CONTEXT_INVALID")
    if not all(
        isinstance(session_context.get(key), str) and session_context[key]
        for key in ("userId", "workspaceId", "expiresAt")
    ):
        raise LauncherBootstrapError("LAUNCHER_SESSION_CONTEXT_ID_INVALID")
    if not all(
        isinstance(session_context.get(key), list)
        and all(isinstance(item, str) for item in session_context[key])
        for key in ("roles", "scopes")
    ):
        raise LauncherBootstrapError("LAUNCHER_SESSION_CONTEXT_PERMISSIONS_INVALID")
    for optional_key in ("deviceId", "dataScopeId"):
        if optional_key in session_context and not isinstance(session_context[optional_key], str):
            raise LauncherBootstrapError("LAUNCHER_SESSION_CONTEXT_OPTIONAL_INVALID")

    return dict(session_context)


def _verify_sqlite_integrity(path: Path) -> None:
    connection = None
    try:
        connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        result = connection.execute("PRAGMA integrity_check").fetchone()
        if not result or result[0] != "ok":
            raise LegacyDatabaseMigrationError("LEGACY_DATABASE_INTEGRITY_FAILED")
    except (sqlite3.Error, OSError) as error:
        raise LegacyDatabaseMigrationError("LEGACY_DATABASE_INTEGRITY_FAILED") from error
    finally:
        if connection is not None:
            connection.close()


def migrate_legacy_database(destination: Path, candidates: list[Path]) -> str:
    destination = destination.resolve(strict=False)
    if destination.exists():
        _verify_sqlite_integrity(destination)
        return "existing"

    legacy = next(
        (
            candidate.resolve(strict=False)
            for candidate in candidates
            if candidate.exists() and candidate.resolve(strict=False) != destination
        ),
        None,
    )
    if legacy is None:
        return "new"

    _verify_sqlite_integrity(legacy)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(f"{destination}.migrating")
    try:
        if temporary.exists():
            temporary.unlink()
        shutil.copy2(legacy, temporary)
        _verify_sqlite_integrity(temporary)
        os.replace(temporary, destination)
        _verify_sqlite_integrity(destination)
    except LegacyDatabaseMigrationError:
        if temporary.exists():
            temporary.unlink()
        raise
    except OSError as error:
        if temporary.exists():
            temporary.unlink()
        raise LegacyDatabaseMigrationError("LEGACY_DATABASE_COPY_FAILED") from error
    return "migrated"


def is_authorized_request(
    *,
    client_host: str,
    host_header: str,
    origin_header: str | None,
    expected_origin: str,
    presented_secret: str,
    expected_secret: str,
) -> bool:
    parsed = urlsplit(expected_origin)
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.port is None:
        return False
    if client_host != "127.0.0.1" or host_header != parsed.netloc:
        return False
    if origin_header and origin_header != expected_origin:
        return False
    if not isinstance(presented_secret, str) or not isinstance(expected_secret, str):
        return False
    return hmac.compare_digest(presented_secret, expected_secret)
