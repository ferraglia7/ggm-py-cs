"""
unity_import — write the generated C# file into the Unity project.
If patching, overwrites the target script.
If new, writes to Assets/SourceFiles/Scripts/Generated/.
Emits [FILES] and [DIFF] lines for ggm-fe.
"""
import json
from pathlib import Path


def run(ctx: dict) -> dict:
    project_path = ctx["project_path"]
    inputs       = ctx["inputs"]
    outputs      = ctx["outputs"]

    gen       = outputs.get("generate_code", {})
    existing  = outputs.get("read_existing", {})
    code      = gen.get("code", "")
    diff      = gen.get("diff", "")
    class_name = gen.get("className", inputs.get("name", "GeneratedScript"))
    is_new    = gen.get("isNewFile", True)

    if not code:
        raise ValueError("generate_code step produced no code")

    # Determine destination path
    target_path = existing.get("targetPath", "")
    if target_path and not is_new:
        # Patch mode: overwrite existing file
        dest = Path(project_path) / Path(target_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(code, encoding="utf-8")
        unity_path = target_path
        print(f"[unity_import] Patched {unity_path}")
    else:
        # New file
        if not class_name.endswith(".cs"):
            filename = class_name + ".cs"
        else:
            filename = class_name

        gen_dir = Path(project_path) / "Assets" / "SourceFiles" / "Scripts" / "Generated"
        gen_dir.mkdir(parents=True, exist_ok=True)
        dest = gen_dir / filename
        dest.write_text(code, encoding="utf-8")
        unity_path = f"Assets/SourceFiles/Scripts/Generated/{filename}"
        print(f"[unity_import] Wrote {unity_path}")

    result = {"scriptPath": unity_path}

    # Emit [FILES] for pluginRunner.ts asset registry
    print(f"[FILES] {json.dumps(result)}")

    # Emit [DIFF] so frontend can display it
    if diff:
        # Encode diff as single-line JSON string to not break log parsing
        print(f"[DIFF] {json.dumps(diff)}")

    return result
