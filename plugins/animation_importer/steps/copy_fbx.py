"""
copy_fbx — copy FBX files to the Unity project Assets folder.
"""
import shutil
from pathlib import Path


def run(ctx: dict) -> dict:
    project_path = ctx["project_path"]
    inputs       = ctx["inputs"]
    outputs      = ctx["outputs"]

    name        = inputs.get("name", "Character")
    output_path = inputs.get("outputPath", "Assets/Animations/Characters/").strip("/") or "Assets/Animations/Characters"
    clips       = outputs.get("scan_fbx", {}).get("clips", [])

    if not clips:
        raise ValueError("No clips to copy — scan_fbx step must run first")

    # Destination: outputPath/{CharacterName}/
    dest_dir = Path(project_path) / output_path.replace("Assets/", "") / name
    dest_dir.mkdir(parents=True, exist_ok=True)

    imported_paths = []
    for clip in clips:
        src  = Path(clip["path"])
        dest = dest_dir / src.name
        shutil.copy2(src, dest)
        unity_path = f"{output_path.rstrip('/')}/{name}/{src.name}"
        imported_paths.append({
            "unityPath": unity_path,
            "animName":  clip["animName"],
            "filename":  src.name,
        })
        print(f"[copy_fbx] {src.name} → {unity_path}")

    print(f"[copy_fbx] Copied {len(imported_paths)} FBX files")
    return {"importedPaths": imported_paths}
