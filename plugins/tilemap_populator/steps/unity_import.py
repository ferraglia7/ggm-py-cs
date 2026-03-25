"""
unity_import — write the C# Editor script and layout JSON to the Unity project.
"""
import json
from pathlib import Path


def run(ctx: dict) -> dict:
    project_path = ctx["project_path"]
    inputs       = ctx["inputs"]
    outputs      = ctx["outputs"]

    name       = inputs.get("name", "Level")
    cs_out     = outputs.get("generate_cs", {})
    layout_out = outputs.get("generate_layout", {})

    code       = cs_out.get("code", "")
    grid       = layout_out.get("grid", [])
    tile_count = cs_out.get("tileCount", 0)

    if not code:
        raise ValueError("No C# code generated")

    # Write C# Editor script
    editor_dir = Path(project_path) / "Assets" / "Editor" / "GGM"
    editor_dir.mkdir(parents=True, exist_ok=True)

    cs_filename = f"Populate_{name}.cs"
    cs_path     = editor_dir / cs_filename
    cs_path.write_text(code, encoding="utf-8")
    unity_cs_path = f"Assets/Editor/GGM/{cs_filename}"
    print(f"[unity_import] Wrote {unity_cs_path}")

    # Write layout JSON (for reference / re-use)
    levels_dir = Path(project_path) / "Assets" / "Levels" / "Layouts"
    levels_dir.mkdir(parents=True, exist_ok=True)
    layout_filename = f"{name}_layout.json"
    layout_path = levels_dir / layout_filename
    layout_path.write_text(json.dumps({"name": name, "grid": grid}, indent=2), encoding="utf-8")
    unity_layout_path = f"Assets/Levels/Layouts/{layout_filename}"
    print(f"[unity_import] Wrote {unity_layout_path}")

    print(f"[FILES] {json.dumps({'scriptPath': unity_cs_path})}")
    return {
        "scriptPath": unity_cs_path,
        "layoutPath": unity_layout_path,
        "tileCount":  tile_count,
    }
