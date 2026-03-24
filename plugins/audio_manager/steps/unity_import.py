"""
Step: unity_import
Copies audio file into Unity project under Assets/Audio/.
"""
import json
import shutil
from pathlib import Path
from engines.unity import to_unity_path


TYPE_SUBFOLDER = {
    "music":   "Music",
    "sfx":     "SFX",
    "voice":   "Voice",
    "ambient": "Ambient",
}


def run(ctx: dict) -> dict:
    project_path = ctx["project_path"]
    inputs = ctx["inputs"]
    outputs = ctx["outputs"]

    track_name = inputs["name"]
    audio_type = inputs.get("audioType", "music")
    audio_tmp = outputs.get("post_process", {}).get("audioTmpPath") or \
                outputs.get("generate_audio", {}).get("audioTmpPath", "")

    if not audio_tmp or not Path(audio_tmp).exists():
        raise RuntimeError("No audio file to import")

    subfolder = TYPE_SUBFOLDER.get(audio_type, "SFX")
    dest_dir = Path(project_path) / "Assets" / "Audio" / subfolder
    dest_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(audio_tmp).suffix
    dest = dest_dir / f"{track_name}{ext}"
    shutil.copy2(audio_tmp, dest)
    print(f"[unity_import] Audio → {dest}")

    unity_path = to_unity_path(project_path, str(dest))
    print(f"[FILES] {json.dumps([unity_path])}")
    return {"audioPath": unity_path}
