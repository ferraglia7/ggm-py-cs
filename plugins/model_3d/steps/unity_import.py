"""
Step: unity_import
Writes recipe_meta.json (triggers RecipeImporter.cs) or invokes Unity batch mode
depending on configuration.
"""

import json
from pathlib import Path
from engines.unity import to_unity_path


PLATE_MAP = {
    "meat":       "Plate_Meat",
    "fish":       "Plate_Fish",
    "drink":      "Plate_Drink",
    "wheat":      "Plate_Wheat",
    "vegetables": "Plate_Vegetable",
    # Generic fallback for non-food assets
    "weapon":     None,
    "prop":       None,
    "character":  None,
}


def run(ctx: dict) -> dict:
    project_path = ctx["project_path"]
    inputs = ctx["inputs"]
    outputs = ctx["outputs"]

    asset_name = inputs["name"]
    classify_out = outputs.get("classify", {})
    download_out = outputs.get("download_assets", {})

    asset_type = classify_out.get("assetType", "prop")
    recipe_category = classify_out.get("recipeCategory")

    fbx_path    = download_out.get("fbxPath", "")
    icon_path   = download_out.get("iconPath", "")
    base_tex    = download_out.get("baseTexture", "")
    metallic    = download_out.get("metallicTexture", "")
    normal      = download_out.get("normalTexture", "")
    asset_folder = download_out.get("assetFolder", "")

    # Write metadata JSON to trigger RecipeImporter.cs (Unity FileSystemWatcher)
    meta = {
        "recipe_name":      asset_name,
        "recipe_type":      recipe_category or asset_type,
        "plate_prefab":     PLATE_MAP.get(recipe_category or "", None),
        "fbx_path":         to_unity_path(project_path, fbx_path),
        "base_texture":     to_unity_path(project_path, base_tex),
        "metallic_texture": to_unity_path(project_path, metallic),
        "normal_texture":   to_unity_path(project_path, normal),
        "icon_path":        to_unity_path(project_path, icon_path),
    }

    if asset_folder:
        meta_path = Path(asset_folder) / "recipe_meta.json"
        meta_path.write_text(json.dumps(meta, indent=2))
        print(f"[unity_import] Metadata written: {meta_path}")
        print(f"[unity_import] Unity will auto-import via RecipeImporter.cs")

    prefab_path = f"Assets/Prefabs/Generated3D/{asset_name}/{asset_name}.prefab"

    # Emit [FILES] line for ggm-fe run tracker
    files = [
        to_unity_path(project_path, fbx_path),
        to_unity_path(project_path, base_tex),
        to_unity_path(project_path, metallic),
        to_unity_path(project_path, normal),
        to_unity_path(project_path, icon_path),
        prefab_path,
    ]
    print(f"[FILES] {json.dumps([f for f in files if f])}")

    return {"prefabPath": prefab_path}
