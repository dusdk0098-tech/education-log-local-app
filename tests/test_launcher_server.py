import json
import os
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from pathlib import Path
from urllib import error, request


def terminate_process_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        process.kill()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


class LauncherHostedServerTests(unittest.TestCase):
    def test_launcher_host_skips_legacy_self_update_before_ready(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "server.py").read_text(encoding="utf-8")
        self.assertIn("if not launcher_hosted and apply_startup_update():", source)

    def test_hosted_server_uses_dynamic_loopback_port_and_secret_header(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            secret = "e" * 64
            process = subprocess.Popen(
                [sys.executable, "server.py", "--launcher-host", "--port", "0", "--no-browser"],
                cwd=Path(__file__).resolve().parents[1],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
            try:
                bootstrap = {
                    "dataDir": str(Path(temp_dir).resolve()),
                    "backendSecret": secret,
                    "sessionContext": {
                        "userId": "user-1",
                        "workspaceId": "workspace-1",
                        "roles": ["member"],
                        "scopes": ["app:pedit-edu:run"],
                        "expiresAt": "2026-07-20T00:00:00.000Z",
                    },
                }
                assert process.stdin is not None
                process.stdin.write((json.dumps(bootstrap) + "\n").encode("utf-8"))
                process.stdin.flush()
                process.stdin.close()
                assert process.stdout is not None
                reader = ThreadPoolExecutor(max_workers=1)
                try:
                    raw_ready = reader.submit(process.stdout.readline).result(timeout=10)
                except FutureTimeoutError as exc:
                    terminate_process_tree(process)
                    self.fail(f"backend ready timeout: {exc}")
                finally:
                    reader.shutdown(wait=False, cancel_futures=True)
                self.assertLessEqual(len(raw_ready), 16_384)
                self.assertTrue(raw_ready.endswith(b"\n"))
                self.assertNotIn(b"\r", raw_ready)
                self.assertNotIn(secret.encode("ascii"), raw_ready)
                self.assertTrue(raw_ready.startswith(b"{"), raw_ready[:80].decode("utf-8", "replace"))
                ready = json.loads(raw_ready.decode("utf-8"))
                self.assertEqual(ready["type"], "backend.ready")
                self.assertEqual(ready["host"], "127.0.0.1")
                self.assertGreater(ready["port"], 0)
                origin = f"http://127.0.0.1:{ready['port']}"

                with self.assertRaises(error.HTTPError) as denied:
                    request.urlopen(f"{origin}/api/bootstrap", timeout=5)
                self.assertEqual(denied.exception.code, 403)
                denied.exception.close()

                authenticated = request.Request(
                    f"{origin}/api/bootstrap",
                    headers={
                        "Origin": origin,
                        "X-Pedit-Backend-Session": secret,
                    },
                )
                with request.urlopen(authenticated, timeout=5) as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(response.headers.get("Content-Security-Policy"), "default-src 'none'")

                update_request = request.Request(
                    f"{origin}/api/update/status",
                    headers={
                        "Origin": origin,
                        "X-Pedit-Backend-Session": secret,
                    },
                )
                with request.urlopen(update_request, timeout=5) as response:
                    update_status = json.load(response)
                self.assertEqual(update_status["managedByLauncher"], True)
                self.assertEqual(update_status["autoUpdateEnabled"], False)
                self.assertEqual(update_status["manifestUrl"], "")

                renewal_body = json.dumps(
                    {
                        "userId": "user-1",
                        "workspaceId": "workspace-1",
                        "roles": ["member"],
                        "scopes": ["app:pedit-edu:run"],
                        "expiresAt": "2026-07-20T01:00:00.000Z",
                    }
                ).encode("utf-8")
                renewal_request = request.Request(
                    f"{origin}/__launcher/session/renew",
                    data=renewal_body,
                    method="POST",
                    headers={
                        "Content-Type": "application/json",
                        "Origin": origin,
                        "X-Pedit-Backend-Session": secret,
                    },
                )
                with request.urlopen(renewal_request, timeout=5) as response:
                    renewal = json.load(response)
                self.assertEqual(renewal, {"renewed": True})

                shutdown_request = request.Request(
                    f"{origin}/__launcher/shutdown/prepare",
                    data=b"{}",
                    method="POST",
                    headers={
                        "Content-Type": "application/json",
                        "Origin": origin,
                        "X-Pedit-Backend-Session": secret,
                    },
                )
                with request.urlopen(shutdown_request, timeout=5) as response:
                    shutdown = json.load(response)
                self.assertEqual(shutdown, {"stopping": True})
                with self.assertRaises(error.HTTPError) as stopping_error:
                    request.urlopen(authenticated, timeout=5)
                self.assertEqual(stopping_error.exception.code, 503)
                stopping_error.exception.close()
            finally:
                terminate_process_tree(process)
                if process.stdout is not None:
                    process.stdout.close()
                if process.stderr is not None:
                    process.stderr.close()


if __name__ == "__main__":
    unittest.main()
