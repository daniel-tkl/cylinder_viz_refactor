from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional
from urllib import error, request


def build_streamlit_command(app_file: Path, port: int) -> list[str]:
    return [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_file),
        "--server.headless=true",
        f"--server.port={port}",
        "--browser.gatherUsageStats=false",
        "--global.developmentMode=false",
    ]


def read_url(url: str, timeout: float = 1.5) -> Optional[bytes]:
    try:
        with request.urlopen(url, timeout=timeout) as response:
            return response.read()
    except (error.URLError, TimeoutError, OSError):
        return None


def wait_for_streamlit(port: int, timeout_seconds: int) -> bool:
    deadline = time.time() + timeout_seconds
    health_url = f"http://127.0.0.1:{port}/_stcore/health"
    root_url = f"http://127.0.0.1:{port}/"

    while time.time() < deadline:
        health_data = read_url(health_url)
        if health_data is not None and b"ok" in health_data.lower():
            root_data = read_url(root_url)
            if root_data is not None and len(root_data) > 0:
                return True
        time.sleep(0.4)

    return False


def stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return

    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def main() -> int:
    parser = argparse.ArgumentParser(description="Streamlit QA smoke automation")
    parser.add_argument("--port", type=int, default=8510, help="Port used for temporary QA run")
    parser.add_argument("--timeout", type=int, default=90, help="Timeout in seconds")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    app_file = repo_root / "streamlit_app.py"

    if not app_file.exists():
        print(f"[QA][FAIL] Streamlit app not found: {app_file}")
        return 2

    command = build_streamlit_command(app_file, port=args.port)
    print("[QA] Starting Streamlit smoke run...")
    print(f"[QA] Command: {' '.join(command)}")

    env = os.environ.copy()
    env.setdefault("STREAMLIT_GLOBAL_DEVELOPMENTMODE", "false")
    env.setdefault("STREAMLIT_BROWSER_GATHERUSAGESTATS", "false")

    process = subprocess.Popen(
        command,
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
    )

    try:
        ready = wait_for_streamlit(port=args.port, timeout_seconds=args.timeout)
        if not ready:
            print(f"[QA][FAIL] Streamlit did not become ready within {args.timeout}s on port {args.port}.")
            return 1

        print(f"[QA][PASS] Streamlit is healthy on http://127.0.0.1:{args.port}/")
        return 0
    finally:
        stop_process(process)


if __name__ == "__main__":
    raise SystemExit(main())
