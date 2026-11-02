"""Shared helpers for the template's tests. Stdlib only."""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def bash() -> str:
    """Absolute path to bash. On Windows a bare "bash" can resolve to WSL's System32
    launcher before PATH is searched, so always use the PATH lookup result."""
    found = shutil.which("bash")
    if not found:
        raise RuntimeError("bash not found on PATH (on Windows, install Git for Windows)")
    return found
