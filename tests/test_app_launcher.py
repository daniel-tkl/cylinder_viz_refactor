from __future__ import annotations

from pathlib import Path

from scripts import app_launcher


def test_build_streamlit_argv_includes_expected_flags() -> None:
    argv = app_launcher.build_streamlit_argv(Path("streamlit_app.py"), port=8600)

    assert argv[0:3] == ["streamlit", "run", "streamlit_app.py"]
    assert "--server.headless=true" in argv
    assert "--server.port=8600" in argv
    assert "--browser.gatherUsageStats=false" in argv
    assert "--global.developmentMode=false" in argv


def test_main_returns_2_when_app_file_is_missing(monkeypatch) -> None:
    monkeypatch.setattr(app_launcher, "resource_path", lambda _relative: Path("missing_app.py"))

    exit_code = app_launcher.main()

    assert exit_code == 2
