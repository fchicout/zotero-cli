import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest


@pytest.mark.e2e
def test_serve_command_lifecycle(run_cli, timestamp):
    """
    Verifies that 'zotero-cli serve' starts a server and responds to health check.
    """
    # 1. Start Server in Background
    # We can't use run_cli directly because it blocks until completion.
    # We need Popen.

    cwd = Path.cwd()
    src_path = str(cwd / "src")
    env = os.environ.copy()
    env["PYTHONPATH"] = src_path

    port = 1970 + (timestamp % 100)  # Semi-random port to avoid collision

    print(f"Starting server on port {port}...")
    proc = subprocess.Popen(
        [sys.executable, "-m", "zotero_cli.cli.main", "serve", "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        text=True,
    )

    try:
        # 2. Wait for Startup
        # Poll /health until 200 or timeout
        base_url = f"http://127.0.0.1:{port}"
        health_url = f"{base_url}/health"

        start = time.time()
        connected = False
        while time.time() - start < 15:
            try:
                resp = httpx.get(health_url, timeout=1.0)
                if resp.status_code == 200:
                    connected = True
                    break
            except (httpx.ConnectError, httpx.TimeoutException):
                time.sleep(0.5)

        assert connected, f"Server failed to start on port {port} within 10s"

        # 3. Test Endpoints
        # /items
        resp_items = httpx.get(f"{base_url}/items")
        assert resp_items.status_code == 200
        # Should return a list (empty or not, depending on config)
        assert isinstance(resp_items.json(), list)

        # /collections
        resp_coll = httpx.get(f"{base_url}/collections")
        assert resp_coll.status_code == 200
        assert isinstance(resp_coll.json(), list)

    finally:
        # 4. Teardown
        print("Stopping server...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

        # Print logs if failed
        if (
            proc.returncode is not None and proc.returncode != 0 and proc.returncode != -15
        ):  # -15 is SIGTERM
            stdout, stderr = proc.communicate()
            print(f"Server STDOUT: {stdout}")
            print(f"Server STDERR: {stderr}")
