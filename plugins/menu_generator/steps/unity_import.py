"""
Step: unity_import
Copies UXML and C# files into the Unity project at the correct paths.
"""

import json
import shutil
from pathlib import Path
from engines.unity import to_unity_path


def run(ctx: dict) -> dict:
    project_path = ctx["project_path"]
    inputs = ctx["inputs"]
    outputs = ctx["outputs"]

    menu_name = inputs["name"]
    uxml_tmp = outputs.get("generate_layout", {}).get("uxmlTmpPath", "")
    cs_tmp = outputs.get("generate_cs", {}).get("csTmpPath", "")

    # Destination paths in Unity project
    ui_dir = Path(project_path) / "Assets" / "UI" / "Menus" / menu_name
    scripts_dir = Path(project_path) / "Assets" / "SourceFiles" / "Scripts" / "UI" / "Menus"
    ui_dir.mkdir(parents=True, exist_ok=True)
    scripts_dir.mkdir(parents=True, exist_ok=True)

    uxml_dest = ui_dir / f"{menu_name}.uxml"
    cs_dest = scripts_dir / f"{menu_name}Controller.cs"

    if uxml_tmp and Path(uxml_tmp).exists():
        shutil.copy2(uxml_tmp, uxml_dest)
        print(f"[unity_import] UXML → {uxml_dest}")
    else:
        print("[unity_import] WARNING: no UXML file to copy")

    if cs_tmp and Path(cs_tmp).exists():
        shutil.copy2(cs_tmp, cs_dest)
        print(f"[unity_import] C# → {cs_dest}")
    else:
        print("[unity_import] WARNING: no C# file to copy")

    uxml_unity = to_unity_path(project_path, str(uxml_dest))
    cs_unity = to_unity_path(project_path, str(cs_dest))

    files = [uxml_unity, cs_unity]
    print(f"[FILES] {json.dumps([f for f in files if f])}")

    return {
        "uxmlPath": uxml_unity,
        "csPath": cs_unity,
    }
