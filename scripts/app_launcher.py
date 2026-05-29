"""Executable launcher for the Streamlit Cylinder Viz app.

This tiny entrypoint runs `streamlit run streamlit_app.py` programmatically so
we can package everything into a single Windows `.exe` using PyInstaller.

Notes
- We resolve the bundled `streamlit_app.py` location at runtime whether running
    from source or a PyInstaller onefile build (using `_MEIPASS`).
- We auto-open the browser to reduce friction for non-technical users.
- We pre-import cylinder domain and shared modules so PyInstaller includes them.
"""

from __future__ import annotations

import io
import logging
import os
import sys
import threading
import time
import tempfile
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import List, TextIO
import socket
import http.client

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Ensure PyInstaller bundles these internal modules (referenced by the app file)
try:
    import src.cylinder_domain.aggregation as _domain_aggregation  # noqa: F401
    import src.cylinder_domain.parsing as _domain_parsing  # noqa: F401
    import src.cylinder_domain.visualization as _domain_visualization  # noqa: F401
    import src.shared.view as _shared_view  # noqa: F401
except Exception:  # noqa: BLE001
    # Silently continue when optional bundle imports are unavailable.
    pass

from streamlit.web import cli as stcli

# Optional PyInstaller splash screen API (present only if built with --splash)
try:  # noqa: SIM105
    import pyi_splash  # type: ignore
except Exception:  # noqa: BLE001
    pyi_splash = None  # type: ignore

logger = logging.getLogger("app_launcher")
logging.basicConfig(level=logging.INFO)


def resource_path(relative: str) -> Path:
    """Return absolute path to a bundled resource.

    In PyInstaller onefile mode, uses `_MEIPASS`. When running from source,
    try repo root (parent of `scripts/`) first, falling back to the script dir.
    """
    # PyInstaller extraction dir
    if hasattr(sys, "_MEIPASS"):
        base = Path(getattr(sys, "_MEIPASS"))  # type: ignore[attr-defined]
        candidate = base / relative
        return candidate

    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent
    candidates = [repo_root / relative, script_dir / relative]
    for c in candidates:
        if c.exists():
            return c
    # Default to repo root path even if missing; caller will log error
    return candidates[0]


def _open_browser_later(url: str, delay_secs: float = 1.0) -> None:
    """Open default web browser after a short delay.

    Parameters
    - url: Target URL.
    - delay_secs: Delay to give the server time to start.
    """
    def _run() -> None:
        time.sleep(max(delay_secs, 0.0))
        try:
            webbrowser.open(url, new=1)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to open browser for %s", url)

    threading.Thread(target=_run, daemon=True).start()


def _open_browser_when_ready(host: str, port: int, timeout_secs: float = 180.0) -> None:
    """Poll the local server until ready, then open the browser and close splash.

    Parameters
    - host: Server host to poll (e.g., "127.0.0.1").
    - port: TCP port to poll.
    - timeout_secs: Max time to wait for readiness.
    """
    def _is_ready() -> bool:
        try:
            conn = http.client.HTTPConnection(host, port, timeout=1.5)
            conn.request("HEAD", "/")
            resp = conn.getresponse()
            return resp.status in (200, 302, 404)
        except Exception:
            return False
        finally:
            try:
                conn.close()  # type: ignore[name-defined]
            except Exception:
                pass

    def _run() -> None:
        start = time.time()
        if pyi_splash:
            try:
                pyi_splash.update_text("Starting CylinderViz…")
            except Exception:
                pass

        while time.time() - start < timeout_secs:
            if _is_ready():
                try:
                    webbrowser.open(f"http://localhost:{port}", new=1)
                except Exception:
                    logger.exception("Failed to open browser for localhost:%s", port)
                if pyi_splash:
                    try:
                        pyi_splash.close()
                    except Exception:
                        pass
                return
            time.sleep(0.25)

        # Timed out; attempt to open the browser anyway and close splash
        try:
            webbrowser.open(f"http://localhost:{port}", new=1)
        except Exception:
            logger.exception("Failed to open browser after timeout for localhost:%s", port)
        if pyi_splash:
            try:
                pyi_splash.close()
            except Exception:
                pass

    threading.Thread(target=_run, daemon=True).start()


def build_streamlit_argv(app_path: Path, port: int = 8501) -> List[str]:
    """Construct argv array for invoking Streamlit CLI programmatically.

    Sets `global.developmentMode=false` to avoid conflicts with `server.port`.
    """
    return [
        "streamlit",
        "run",
        str(app_path),
        "--server.headless=true",
        f"--server.port={port}",
        "--browser.gatherUsageStats=false",
        "--global.developmentMode=false",
    ]


def _pick_server_port(preferred: int = 8501, max_scan: int = 20) -> int:
    """Pick an available TCP port for the Streamlit server.

    Tries `preferred` first, then scans subsequent ports up to `preferred+max_scan`.
    If none are free, asks the OS to assign an ephemeral port.
    """
    def _is_listening(p: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            try:
                s.connect(("127.0.0.1", p))
                return True
            except OSError:
                return False

    # Prefer the requested port if not currently in use
    if not _is_listening(preferred):
        return preferred
    # Fallback: ask OS for an ephemeral port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _logs_dir() -> Path:
    """Determine a writable logs directory for the packed app."""
    local_appdata = os.environ.get("LOCALAPPDATA")
    base = Path(local_appdata) if local_appdata else Path(tempfile.gettempdir())
    target = base / "CylinderViz" / "logs"
    target.mkdir(parents=True, exist_ok=True)
    return target


class TeeToFile(io.TextIOBase):
    """Tee stdout/stderr to a file while preserving original stream."""

    def __init__(self, file_handle: TextIO, original: TextIO) -> None:
        super().__init__()
        self._file = file_handle
        self._orig = original

    def write(self, s: str) -> int:  # type: ignore[override]
        try:
            self._file.write(s)
            self._file.flush()
        except Exception:
            pass
        try:
            return self._orig.write(s)
        except Exception:
            return 0

    def flush(self) -> None:  # type: ignore[override]
        try:
            self._file.flush()
        except Exception:
            pass
        try:
            self._orig.flush()
        except Exception:
            pass


def main() -> int:
    """Launch the Streamlit app.

    Returns process exit code.
    """
    
    app_file = resource_path("streamlit_app.py")
    
    if not app_file.exists():
        logger.error("Could not locate app file at %s", app_file)
        return 2

    # Set Streamlit config via env to be extra safe in packaged mode
    os.environ.setdefault("STREAMLIT_GLOBAL_DEVELOPMENTMODE", "false")
    os.environ.setdefault("STREAMLIT_BROWSER_GATHERUSAGESTATS", "false")

    # Prepare logging to file and tee stdout/stderr
    logs_dir = _logs_dir()
    log_path = logs_dir / f"cylinderviz_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    fh: TextIO
    fh = log_path.open("a", encoding="utf-8")
    logging.getLogger().addHandler(logging.FileHandler(log_path, encoding="utf-8"))
    sys.stdout = TeeToFile(fh, sys.__stdout__)  # type: ignore[assignment]
    sys.stderr = TeeToFile(fh, sys.__stderr__)  # type: ignore[assignment]
    logger.info("Logging to %s", log_path)
    logger.info("Using app file: %s", app_file)

    # Choose a server port that's free
    port = _pick_server_port(preferred=8501, max_scan=50)
    logger.info("Using server port: %s", port)
    
    # Provide early splash feedback (if present)
    if pyi_splash:
        try:
            pyi_splash.update_text(f"Launching server on port {port}…")
        except Exception:
            pass

    # Open browser once server is reachable; also closes splash if present
    _open_browser_when_ready("127.0.0.1", port, timeout_secs=180.0)

    sys.argv = build_streamlit_argv(app_file, port=port)
    logger.info("Starting Streamlit with argv=%s", " ".join(sys.argv))
    try:
        return int(stcli.main())
    except SystemExit as exc:  # Streamlit may call sys.exit
        return int(exc.code or 0)
    except Exception:
        logger.exception("Unhandled exception during Streamlit startup")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
