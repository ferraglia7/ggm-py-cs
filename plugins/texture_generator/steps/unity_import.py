"""
Step: unity_import
Copies texture into Unity and writes a material_meta.json to trigger C# importer.
"""
import json
import shutil
from pathlib import Path
from engines.unity import to_unity_path


def run(ctx: dict) -> dict:
    project_path = ctx["project_path"]
    inputs = ctx["inputs"]
    outputs = ctx["outputs"]

    tex_name = inputs["name"]
    tex_type = inputs.get("textureType", "albedo")
    tex_tmp = outputs.get("post_process", {}).get("textureTmpPath") or \
              outputs.get("generate_texture", {}).get("textureTmpPath", "")

    if not tex_tmp or not Path(tex_tmp).exists():
        raise RuntimeError("No texture file to import")

    # Destination in Unity
    tex_dir = Path(project_path) / "Assets" / "Textures" / "Generated" / tex_name
    tex_dir.mkdir(parents=True, exist_ok=True)

    dest = tex_dir / f"{tex_name}.png"
    shutil.copy2(tex_tmp, dest)
    print(f"[unity_import] Texture → {dest}")

    # Write material_meta.json (can be read by a C# MaterialImporter)
    meta = {
        "texture_name": tex_name,
        "texture_type": tex_type,
        "albedo_path": to_unity_path(project_path, str(dest)),
        "seamless": inputs.get("seamless", True),
    }
    meta_path = tex_dir / "material_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2))

    unity_path = to_unity_path(project_path, str(dest))
    print(f"[FILES] {json.dumps([unity_path])}")
    return {"albedoPath": unity_path, "materialPath": to_unity_path(project_path, str(meta_path))}
