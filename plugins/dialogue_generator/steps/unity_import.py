"""
unity_import — write the dialogue file to Assets/Dialogue/{name}.yarn or .ink
"""
import json
from pathlib import Path


def run(ctx: dict) -> dict:
    project_path = ctx["project_path"]
    inputs       = ctx["inputs"]
    outputs      = ctx["outputs"]

    name    = inputs.get("name", "Dialogue")
    fmt     = outputs.get("generate_dialogue", {}).get("format") or inputs.get("format", "yarn")
    content = outputs.get("generate_dialogue", {}).get("content", "")
    lines   = outputs.get("generate_dialogue", {}).get("lineCount", 0)

    if not content:
        raise ValueError("No dialogue content to write")

    ext     = ".yarn" if fmt == "yarn" else ".ink"
    dest_dir = Path(project_path) / "Assets" / "Dialogue"
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest = dest_dir / f"{name}{ext}"
    dest.write_text(content, encoding="utf-8")

    unity_path = f"Assets/Dialogue/{name}{ext}"
    print(f"[unity_import] Wrote {unity_path} ({lines} lines)")

    print(f"[FILES] {json.dumps({'filePath': unity_path})}")
    return {"filePath": unity_path, "lineCount": lines, "format": fmt}
