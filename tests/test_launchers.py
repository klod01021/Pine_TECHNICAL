from pathlib import Path

from option_pricer.bootstrap import REPO_ROOT, dependencies_ok, venv_python


def test_repo_root_points_at_project():
    assert (REPO_ROOT / "launch.py").is_file()
    assert (REPO_ROOT / "Launch Pricer.command").is_file()
    assert (REPO_ROOT / "Launch Pricer.bat").is_file()
    assert (REPO_ROOT / "Launch Pricer.app" / "Contents" / "MacOS" / "launcher").is_file()
    assert (REPO_ROOT / "requirements.txt").is_file()


def test_mac_command_is_executable_script():
    path = REPO_ROOT / "Launch Pricer.command"
    text = path.read_text(encoding="utf-8")
    assert text.startswith("#!/bin/bash")
    assert "launch.py" in text
    assert path.stat().st_mode & 0o111


def test_windows_bat_finds_python_and_launch_py():
    text = (REPO_ROOT / "Launch Pricer.bat").read_text(encoding="utf-8")
    assert "launch.py" in text
    assert "python.org/downloads" in text
    assert "py -3" in text


def test_mac_app_opens_terminal_command():
    launcher = (
        REPO_ROOT / "Launch Pricer.app" / "Contents" / "MacOS" / "launcher"
    ).read_text(encoding="utf-8")
    plist = (REPO_ROOT / "Launch Pricer.app" / "Contents" / "Info.plist").read_text(
        encoding="utf-8"
    )
    assert "open -a Terminal" in launcher
    assert "Launch Pricer.command" in launcher
    assert "CFBundleExecutable" in plist
    assert (REPO_ROOT / "Launch Pricer.app" / "Contents" / "MacOS" / "launcher").stat().st_mode & 0o111


def test_venv_python_path_matches_platform_layout():
    python = venv_python()
    assert python.name.startswith("python")
    assert ".venv" in python.parts


def test_current_interpreter_has_runtime_deps():
    assert dependencies_ok()
