"""
unity_import — write the C# ScriptableObject class to the Unity project.
Optionally writes a recipe_meta.json trigger for .asset instance creation.
"""
import json
from pathlib import Path


def run(ctx: dict) -> dict:
    project_path = ctx["project_path"]
    inputs       = ctx["inputs"]
    outputs      = ctx["outputs"]

    gen    = outputs.get("generate_cs", {})
    code   = gen.get("code", "")
    cname  = gen.get("className", inputs.get("name", "GeneratedSO"))
    ns     = gen.get("namespace", "RestaurantRoguelite.Data")

    if not code:
        raise ValueError("generate_cs step produced no code")

    # Destination: Assets/SourceFiles/Scripts/Data/Generated/
    data_dir = Path(project_path) / "Assets" / "SourceFiles" / "Scripts" / "Data" / "Generated"
    data_dir.mkdir(parents=True, exist_ok=True)

    script_abs  = data_dir / f"{cname}.cs"
    script_abs.write_text(code, encoding="utf-8")
    print(f"[unity_import] Wrote {script_abs}")

    # Unity-relative path (forward slashes)
    script_unity = "Assets/SourceFiles/Scripts/Data/Generated/" + cname + ".cs"

    result: dict = {"scriptPath": script_unity}

    # Optionally write a meta trigger for .asset creation
    if inputs.get("createAsset", True):
        asset_dir = Path(project_path) / "Assets" / "SourceFiles" / "Scripts" / "Data" / "Generated"
        meta_path = asset_dir / f"{cname}_create_asset.json"
        meta_path.write_text(json.dumps({
            "action":    "create_asset",
            "className": f"{ns}.{cname}",
            "assetPath": f"Assets/SourceFiles/Data/Generated/{cname}.asset",
        }, indent=2), encoding="utf-8")
        asset_unity = f"Assets/SourceFiles/Data/Generated/{cname}.asset"
        result["assetPath"] = asset_unity
        print(f"[unity_import] Asset trigger written → {meta_path.name}")

    # Emit FILES line for pluginRunner.ts
    print(f"[FILES] {json.dumps(result)}")
    return result
