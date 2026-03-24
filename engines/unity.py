"""
Unity Engine Adapter
====================
Handles all Unity-specific operations:
- Path resolution (Assets/ relative paths)
- Invoking Unity batch mode to run C# Editor scripts
- Reading Unity project metadata
"""

import os
import subprocess
import json
from pathlib import Path


def assets_path(project_path: str) -> Path:
    """Returns the Assets/ directory of the Unity project."""
    return Path(project_path) / "Assets"


def to_unity_path(project_path: str, abs_path: str) -> str:
    """Convert an absolute filesystem path to a Unity-relative Assets/... path."""
    try:
        rel = Path(abs_path).relative_to(Path(project_path))
        return str(rel).replace("\\", "/")
    except ValueError:
        return abs_path.replace("\\", "/")


def read_project_version(project_path: str) -> str | None:
    """Read Unity version from ProjectSettings/ProjectVersion.txt."""
    version_file = Path(project_path) / "ProjectSettings" / "ProjectVersion.txt"
    if not version_file.exists():
        return None
    for line in version_file.read_text().splitlines():
        if line.startswith("m_EditorVersion:"):
            return line.split(":", 1)[1].strip()
    return None


def find_unity_executable() -> str | None:
    """Try to find Unity.exe in common installation paths."""
    candidates = [
        r"C:\Program Files\Unity\Hub\Editor",
        r"C:\Program Files\Unity",
    ]
    for base in candidates:
        base_path = Path(base)
        if not base_path.exists():
            continue
        for version_dir in sorted(base_path.iterdir(), reverse=True):
            exe = version_dir / "Editor" / "Unity.exe"
            if exe.exists():
                return str(exe)
    return None


def run_unity_method(project_path: str, method: str, args_json: dict, unity_exe: str | None = None) -> int:
    """
    Invoke a C# Editor method in Unity batch mode.

    Args:
        project_path: absolute path to Unity project root
        method: fully qualified C# method (e.g. "GGM.Importer.ImportAsset")
        args_json: dict passed as JSON via GGM_ARGS env var
        unity_exe: path to Unity.exe (auto-detected if None)

    Returns:
        Exit code from Unity process
    """
    if not unity_exe:
        unity_exe = find_unity_executable()
    if not unity_exe:
        raise RuntimeError("Unity.exe not found. Set unity_exe parameter or install Unity.")

    env = {**os.environ, "GGM_ARGS": json.dumps(args_json)}
    cmd = [
        unity_exe,
        "-batchmode",
        "-nographics",
        "-projectPath", project_path,
        "-executeMethod", method,
        "-quit",
        "-logFile", str(Path(project_path) / ".ggm" / "unity_batch.log"),
    ]
    print(f"[Unity] Running: {method}")
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        log_path = Path(project_path) / ".ggm" / "unity_batch.log"
        log_content = log_path.read_text() if log_path.exists() else result.stderr
        raise RuntimeError(f"Unity batch mode failed (exit {result.returncode}):\n{log_content[-2000:]}")
    return result.returncode
