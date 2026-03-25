"""
read_existing — if a targetScript is set, read the existing C# file for patching.
Skips gracefully if no targetScript is provided.
"""
from pathlib import Path


def run(ctx: dict) -> dict:
    inputs       = ctx["inputs"]
    project_path = ctx["project_path"]

    target = inputs.get("targetScript", "").strip()
    if not target:
        print("[read_existing] No targetScript — generating new file")
        return {"existingCode": "", "isNewFile": True}

    # Resolve relative to Assets/
    if not target.startswith("Assets/"):
        target = "Assets/" + target.lstrip("/")

    full_path = Path(project_path) / target.replace("/", os.sep if False else "/")
    # Use pathlib for cross-platform
    full_path = Path(project_path) / Path(target)

    if not full_path.exists():
        print(f"[read_existing] File not found: {target} — will create new")
        return {"existingCode": "", "isNewFile": True, "targetPath": target}

    code = full_path.read_text(encoding="utf-8")
    print(f"[read_existing] Read existing script: {target} ({len(code)} chars)")
    return {"existingCode": code, "isNewFile": False, "targetPath": target}


import os
