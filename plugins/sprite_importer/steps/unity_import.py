"""
unity_import — copy processed sprites to Assets/Sprites/Generated/ and
write a .meta trigger JSON for Unity texture importer settings.
"""
import json
import shutil
from pathlib import Path


def run(ctx: dict) -> dict:
    project_path = ctx["project_path"]
    inputs       = ctx["inputs"]
    outputs      = ctx["outputs"]

    # Prefer optimized → sliced → bg-removed → original
    paths = (
        outputs.get("optimize", {}).get("outputPaths")
        or outputs.get("slice",    {}).get("outputPaths")
        or [outputs.get("remove_bg", {}).get("outputPath")]
        or [inputs.get("imagePath")]
    )
    paths = [p for p in paths if p and Path(p).exists()]

    if not paths:
        raise FileNotFoundError("No processed sprite images found")

    sprite_name    = inputs.get("name", "sprite")
    ppu            = int(inputs.get("pixelsPerUnit", "100") or "100")
    filter_mode    = inputs.get("filterMode", "Point")
    slice_mode     = inputs.get("sliceMode", "none")

    # Destination
    dest_dir = Path(project_path) / "Assets" / "Sprites" / "Generated"
    dest_dir.mkdir(parents=True, exist_ok=True)

    imported = []
    for src in paths:
        src_path = Path(src)
        dest = dest_dir / src_path.name
        shutil.copy2(src_path, dest)
        unity_path = f"Assets/Sprites/Generated/{src_path.name}"
        imported.append(unity_path)
        print(f"[unity_import] Copied → {unity_path}")

    # Write importer meta trigger
    meta = {
        "action":       "configure_sprite_importer",
        "sprites":      imported,
        "pixelsPerUnit": ppu,
        "filterMode":   filter_mode,
        "sliceMode":    slice_mode,
        "spriteName":   sprite_name,
    }
    meta_path = dest_dir / f"{sprite_name}_import_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    result = {
        "spritePath": imported[0] if len(imported) == 1 else f"Assets/Sprites/Generated/",
        "spritePaths": imported,
        "sliceCount": len(imported),
    }
    print(f"[FILES] {json.dumps({'spritePath': result['spritePath']})}")
    return result
