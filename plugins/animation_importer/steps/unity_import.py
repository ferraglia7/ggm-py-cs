"""
unity_import — write the AnimatorController C# script and a rig config JSON
that tells Unity how to import the FBX files (rig type, avatar, etc.).
"""
import json
from pathlib import Path


def run(ctx: dict) -> dict:
    project_path   = ctx["project_path"]
    inputs         = ctx["inputs"]
    outputs        = ctx["outputs"]

    name            = inputs.get("name", "Character")
    character_type  = inputs.get("characterType", "Humanoid")
    output_path     = inputs.get("outputPath", "Assets/Animations/Characters/").strip("/")
    generate_anim   = inputs.get("generateAnimator", True)

    imported_paths  = outputs.get("copy_fbx", {}).get("importedPaths", [])
    animator_code   = outputs.get("generate_animator", {}).get("code", "")
    clip_count      = len(imported_paths)

    safe_name       = "".join(c for c in name if c.isalnum() or c == "_")
    dest_unity_dir  = Path(project_path) / output_path.replace("Assets/", "") / name

    animator_unity_path = ""

    # Write AnimatorController setup script
    if generate_anim and animator_code:
        editor_dir = Path(project_path) / "Assets" / "Editor" / "GGM"
        editor_dir.mkdir(parents=True, exist_ok=True)
        cs_filename = f"CreateAnimator_{safe_name}.cs"
        cs_path     = editor_dir / cs_filename
        cs_path.write_text(animator_code, encoding="utf-8")
        animator_unity_path = f"Assets/Editor/GGM/{cs_filename}"
        print(f"[unity_import] Wrote {animator_unity_path}")

    # Write rig config trigger (read by a Unity post-processor)
    rig_config = {
        "action":        "configure_animation_rig",
        "characterName": name,
        "characterType": character_type,  # "Humanoid" or "Generic"
        "clips": [
            {"unityPath": c["unityPath"], "animName": c["animName"]}
            for c in imported_paths
        ],
    }
    rig_config_path = dest_unity_dir / f"{name}_rig_config.json"
    rig_config_path.write_text(json.dumps(rig_config, indent=2), encoding="utf-8")
    rig_config_unity = f"{output_path}/{name}/{name}_rig_config.json"
    print(f"[unity_import] Wrote {rig_config_unity}")
    print(f"[unity_import] {clip_count} clips ready for Unity import")

    print(f"[FILES] {json.dumps({'animatorPath': animator_unity_path or rig_config_unity})}")
    return {
        "animationPaths": [c["unityPath"] for c in imported_paths],
        "animatorPath":   animator_unity_path,
        "clipCount":      clip_count,
    }
