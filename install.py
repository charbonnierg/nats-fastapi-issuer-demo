#!/usr/bin/env python3

import os
import pathlib
import subprocess
import sys
import venv

VENV_DIR = pathlib.Path(__file__).resolve(True).parent / ".venv"


if os.name == "nt":
    VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe"
else:
    VENV_PYTHON = VENV_DIR / "bin" / "python"


def install_virtualenv() -> None:
    """Create a virtualenv and install dependencies"""
    venv.create(
        VENV_DIR,
        system_site_packages=False,
        clear=False,
        symlinks=False,
        with_pip=True,
        prompt=None,
    )
    try:
        subprocess.run(
            [
                VENV_PYTHON,
                "-m",
                "pip",
                "install",
                "-U",
                "pip",
                "setuptools",
                "wheel",
                "build",
            ]
        )
    except Exception:
        # No need to print traceback, error will be printed from subprocess stderr
        sys.exit(1)


def install_project() -> None:
    """Installing project in editable mode using pip"""
    try:
        subprocess.run(
            [VENV_PYTHON, "-m", "pip", "install", "-e", ".[dev,telemetry,oidc]"]
        )
    except Exception:
        # No need to print traceback, error will be printed from subprocess stderr
        sys.exit(1)


if __name__ == "__main__":
    # First make sure virtualenv exists
    install_virtualenv()
    # Then install dependencies from requirements.txt
    install_project()
