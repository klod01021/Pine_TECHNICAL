"""Create a local virtualenv, install requirements, and re-launch with it."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VENV_DIR = REPO_ROOT / ".venv"
REQUIREMENTS = REPO_ROOT / "requirements.txt"
BOOTSTRAP_FLAG = "OPTION_PRICER_BOOTSTRAPPED"
_IMPORT_CHECK = "import QuantLib, vollib, fastapi, uvicorn"


def venv_python() -> Path:
    if sys.platform == "win32":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def in_project_venv() -> bool:
    try:
        return Path(sys.prefix).resolve() == VENV_DIR.resolve()
    except OSError:
        return False


def dependencies_ok(python_exe: str | None = None) -> bool:
    exe = python_exe or sys.executable
    result = subprocess.run(
        [exe, "-c", _IMPORT_CHECK],
        cwd=REPO_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def _install_requirements(python_exe: str) -> None:
    print("Installing QuantLib, vollib, FastAPI, and other packages ...")
    print("First run can take a few minutes.")
    subprocess.check_call([python_exe, "-m", "pip", "install", "--upgrade", "pip"], cwd=REPO_ROOT)
    subprocess.check_call(
        [python_exe, "-m", "pip", "install", "-r", str(REQUIREMENTS)],
        cwd=REPO_ROOT,
    )


def _create_venv() -> Path:
    import venv

    print(f"Creating local environment at {VENV_DIR} ...")
    venv.create(VENV_DIR, with_pip=True)
    python = venv_python()
    if not python.exists():
        raise RuntimeError(f"venv python missing: {python}")
    return python


def _reexec(python: Path, argv: list[str]) -> None:
    os.environ[BOOTSTRAP_FLAG] = "1"
    os.chdir(REPO_ROOT)
    command = [str(python), "-m", "option_pricer", "--no-bootstrap", *argv]
    os.execv(str(python), command)


def reexec_if_needed(argv: list[str]) -> None:
    """Switch into the project venv when the launchers start from system Python."""
    if os.environ.get(BOOTSTRAP_FLAG) == "1" or in_project_venv():
        os.environ[BOOTSTRAP_FLAG] = "1"
        return

    python = venv_python()
    try:
        if not python.exists():
            python = _create_venv()
        if not dependencies_ok(str(python)):
            _install_requirements(str(python))
        if not dependencies_ok(str(python)):
            raise RuntimeError("Dependencies are still missing after install.")
        _reexec(python, argv)
    except Exception as exc:
        print(f"Could not use a local .venv ({exc}).")
        if dependencies_ok(sys.executable):
            print("Using the current Python interpreter instead.")
            os.environ[BOOTSTRAP_FLAG] = "1"
            return
        try:
            print("Installing packages for this Python ...")
            _install_requirements(sys.executable)
            os.environ[BOOTSTRAP_FLAG] = "1"
        except Exception as install_exc:
            raise RuntimeError(
                "Could not prepare the option pricer environment. "
                "Install Python 3 from https://www.python.org/downloads/ "
                f"and try again. ({install_exc})"
            ) from install_exc
