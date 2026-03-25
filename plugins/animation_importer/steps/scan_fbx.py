"""
scan_fbx — scan a folder for Mixamo FBX files and extract animation names.

Mixamo FBX naming conventions:
  "Idle.fbx", "Walking.fbx", "Run Forward.fbx", "Sword And Shield Idle.fbx"
  or with character prefix: "Xbot|Idle.fbx"

Output: list of { filename, animName, path }
"""
from pathlib import Path
import re


def _clean_anim_name(filename: str) -> str:
    """Extract clean animation name from Mixamo filename."""
    stem = Path(filename).stem
    # Remove Mixamo character prefix (e.g. "Xbot|Idle" → "Idle")
    if "|" in stem:
        stem = stem.split("|", 1)[1]
    # PascalCase: "Run Forward" → "RunForward"
    parts = re.split(r"[\s_\-]+", stem)
    return "".join(p.capitalize() for p in parts if p)


def run(ctx: dict) -> dict:
    inputs = ctx["inputs"]

    fbx_folder = inputs.get("fbxFolder", "").strip()
    if not fbx_folder:
        raise ValueError("fbxFolder is required")

    folder = Path(fbx_folder)
    if not folder.exists():
        raise FileNotFoundError(f"FBX folder not found: {fbx_folder}")

    fbx_files = sorted(folder.glob("*.fbx")) + sorted(folder.glob("*.FBX"))

    if not fbx_files:
        raise FileNotFoundError(f"No FBX files found in: {fbx_folder}")

    clips = []
    for f in fbx_files:
        anim_name = _clean_anim_name(f.name)
        clips.append({
            "filename": f.name,
            "animName": anim_name,
            "path":     str(f),
        })
        print(f"[scan_fbx] Found: {f.name} → {anim_name}")

    print(f"[scan_fbx] Total: {len(clips)} FBX files")
    return {"clips": clips, "clipCount": len(clips)}
