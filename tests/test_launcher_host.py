import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import launcher_host


class LauncherHostModuleTests(unittest.TestCase):
    def test_launcher_host_module_exists(self) -> None:
        self.assertIsNotNone(importlib.util.find_spec("launcher_host"))

    def test_parse_bootstrap_accepts_only_safe_session_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            payload = {
                "dataDir": str(Path(temp_dir).resolve()),
                "backendSecret": "a" * 64,
                "sessionContext": {
                    "userId": "user-1",
                    "workspaceId": "workspace-1",
                    "roles": ["member"],
                    "scopes": ["app:pedit-edu:run"],
                    "expiresAt": "2026-07-20T00:00:00.000Z",
                    "deviceId": "device-1",
                    "dataScopeId": "scope-1",
                },
            }

            result = launcher_host.parse_bootstrap_line(json.dumps(payload).encode("utf-8"))

            self.assertEqual(result.data_dir, Path(temp_dir).resolve())
            self.assertEqual(result.backend_secret, "a" * 64)
            self.assertEqual(result.session_context["workspaceId"], "workspace-1")
            self.assertNotIn("appSessionToken", result.session_context)

    def test_parse_bootstrap_rejects_token_fields_and_multiline_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = {
                "dataDir": str(Path(temp_dir).resolve()),
                "backendSecret": "b" * 64,
                "sessionContext": {
                    "userId": "user-1",
                    "workspaceId": "workspace-1",
                    "roles": [],
                    "scopes": ["app:pedit-edu:run"],
                    "expiresAt": "2026-07-20T00:00:00.000Z",
                    "appSessionToken": "must-never-cross",
                },
            }
            with self.assertRaises(launcher_host.LauncherBootstrapError):
                launcher_host.parse_bootstrap_line(json.dumps(base).encode("utf-8"))

            base["sessionContext"].pop("appSessionToken")
            raw = json.dumps(base).encode("utf-8") + b"\n{}"
            with self.assertRaises(launcher_host.LauncherBootstrapError):
                launcher_host.parse_bootstrap_line(raw)

    def test_parse_bootstrap_rejects_oversized_or_invalid_secret(self) -> None:
        with self.assertRaises(launcher_host.LauncherBootstrapError):
            launcher_host.parse_bootstrap_line(b"{" + b" " * 65536 + b"}")
        with tempfile.TemporaryDirectory() as temp_dir:
            payload = {
                "dataDir": str(Path(temp_dir).resolve()),
                "backendSecret": "not-a-secret",
                "sessionContext": {
                    "userId": "user-1",
                    "workspaceId": "workspace-1",
                    "roles": [],
                    "scopes": ["app:pedit-edu:run"],
                    "expiresAt": "2026-07-20T00:00:00.000Z",
                },
            }
            with self.assertRaises(launcher_host.LauncherBootstrapError):
                launcher_host.parse_bootstrap_line(json.dumps(payload).encode("utf-8"))

    def test_legacy_database_is_copied_once_after_integrity_check(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            legacy = root / "legacy" / "education_log.db"
            destination = root / "data" / "education_log.db"
            legacy.parent.mkdir()
            connection = sqlite3.connect(legacy)
            try:
                connection.execute("CREATE TABLE marker(value TEXT NOT NULL)")
                connection.execute("INSERT INTO marker VALUES ('legacy-data')")
                connection.commit()
            finally:
                connection.close()
            original_bytes = legacy.read_bytes()

            result = launcher_host.migrate_legacy_database(destination, [legacy])

            self.assertEqual(result, "migrated")
            self.assertEqual(legacy.read_bytes(), original_bytes)
            connection = sqlite3.connect(destination)
            try:
                self.assertEqual(connection.execute("SELECT value FROM marker").fetchone()[0], "legacy-data")
                self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            finally:
                connection.close()

            connection = sqlite3.connect(destination)
            try:
                connection.execute("UPDATE marker SET value='new-data'")
                connection.commit()
            finally:
                connection.close()
            self.assertEqual(launcher_host.migrate_legacy_database(destination, [legacy]), "existing")
            connection = sqlite3.connect(destination)
            try:
                self.assertEqual(connection.execute("SELECT value FROM marker").fetchone()[0], "new-data")
            finally:
                connection.close()

    def test_corrupt_legacy_database_fails_closed_without_partial_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            legacy = root / "legacy.db"
            destination = root / "data" / "education_log.db"
            legacy.write_bytes(b"not-a-sqlite-database")

            with self.assertRaises(launcher_host.LegacyDatabaseMigrationError):
                launcher_host.migrate_legacy_database(destination, [legacy])

            self.assertFalse(destination.exists())
            self.assertFalse(destination.with_suffix(".db.migrating").exists())

    def test_hosted_request_requires_loopback_exact_origin_and_constant_secret(self) -> None:
        origin = "http://127.0.0.1:49152"
        secret = "c" * 64
        self.assertTrue(
            launcher_host.is_authorized_request(
                client_host="127.0.0.1",
                host_header="127.0.0.1:49152",
                origin_header=origin,
                expected_origin=origin,
                presented_secret=secret,
                expected_secret=secret,
            )
        )
        self.assertFalse(
            launcher_host.is_authorized_request(
                client_host="127.0.0.1",
                host_header="localhost:49152",
                origin_header=origin,
                expected_origin=origin,
                presented_secret=secret,
                expected_secret=secret,
            )
        )
        self.assertFalse(
            launcher_host.is_authorized_request(
                client_host="127.0.0.1",
                host_header="127.0.0.1:49152",
                origin_header="https://attacker.invalid",
                expected_origin=origin,
                presented_secret=secret,
                expected_secret=secret,
            )
        )
        self.assertFalse(
            launcher_host.is_authorized_request(
                client_host="127.0.0.1",
                host_header="127.0.0.1:49152",
                origin_header=None,
                expected_origin=origin,
                presented_secret="d" * 64,
                expected_secret=secret,
            )
        )


if __name__ == "__main__":
    unittest.main()
