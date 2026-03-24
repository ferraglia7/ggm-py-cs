"""
Step: download_assets
Downloads FBX + textures into the Unity project.
"""

import os
import json
import requests
from pathlib import Path


def run(ctx: dict) -> dict:
    project_path = ctx["project_path"]
    inputs = ctx["inputs"]
    outputs = ctx["outputs"]

    asset_name = inputs["name"]
    gen_output = outputs.get("generate_3d", {})
    remesh_output = outputs.get("remesh", {})

    task_data = gen_output.get("taskData", {})
    remesh_data = remesh_output.get("remeshData", {}) if not remesh_output.get("skipped") else {}

    # Determine output folder in Unity
    asset_folder = Path(project_path) / "Assets" / "Prefabs" / "Generated3D" / asset_name
    source_folder = asset_folder / "Source"
    texture_folder = asset_folder / "Textures"
    source_folder.mkdir(parents=True, exist_ok=True)
    texture_folder.mkdir(parents=True, exist_ok=True)

    # Icon (transparent image from remove_bg)
    icon_path = ""
    transparent_path = outputs.get("remove_bg", {}).get("transparentImagePath")
    if transparent_path and Path(transparent_path).exists():
        ui_images = Path(project_path) / "Assets" / "UI" / "Images"
        ui_images.mkdir(parents=True, exist_ok=True)
        icon_dest = ui_images / f"{asset_name}.png"
        icon_dest.write_bytes(Path(transparent_path).read_bytes())
        icon_path = str(icon_dest)
        print(f"[download_assets] Icon saved: {icon_dest}")

    # FBX
    fbx_url = None
    if remesh_data:
        fbx_url = (remesh_data.get("model_urls") or {}).get("fbx")
    if not fbx_url:
        fbx_url = (task_data.get("model_urls") or {}).get("fbx")

    fbx_path = ""
    if fbx_url:
        fbx_dest = source_folder / f"{asset_name}.fbx"
        _download(fbx_url, fbx_dest)
        fbx_path = str(fbx_dest)
        print(f"[download_assets] FBX saved: {fbx_dest}")

    # Textures
    texture_paths = {"base": "", "metallic": "", "normal": ""}
    raw_textures = task_data.get("texture_urls", [])
    tex_dict = raw_textures[0] if (isinstance(raw_textures, list) and raw_textures) else raw_textures

    if isinstance(tex_dict, dict):
        for key, url in tex_dict.items():
            if not url:
                continue
            filename = url.split("?")[0].split("/")[-1]
            dest = texture_folder / filename
            print(f"[download_assets] Texture: {filename}")
            _download(url, dest)
            fn = filename.lower()
            if "texture_normal" in fn:
                texture_paths["normal"] = str(dest)
            elif "metallic" in fn and "roughness" not in fn:
                texture_paths["metallic"] = str(dest)
            elif all(x not in fn for x in ("roughness", "normal", "metallic", "occlusion", "geometry")):
                texture_paths["base"] = str(dest)

    return {
        "fbxPath": fbx_path,
        "iconPath": icon_path,
        "baseTexture": texture_paths["base"],
        "metallicTexture": texture_paths["metallic"],
        "normalTexture": texture_paths["normal"],
        "assetFolder": str(asset_folder),
    }


def _download(url: str, dest: Path):
    r = requests.get(url, stream=True, timeout=60)
    r.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)
