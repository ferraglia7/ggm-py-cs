"""
Step: post_process
Normalizes audio volume. Uses pydub if available, otherwise skips gracefully.
"""
from pathlib import Path


def run(ctx: dict) -> dict:
    outputs = ctx["outputs"]
    audio_tmp = outputs.get("generate_audio", {}).get("audioTmpPath", "")
    if not audio_tmp or not Path(audio_tmp).exists():
        print("[post_process] No audio file found, skipping")
        return {"audioTmpPath": audio_tmp}

    try:
        from pydub import AudioSegment
        from pydub.effects import normalize
        audio = AudioSegment.from_file(audio_tmp)
        normalized = normalize(audio)
        out_path = Path(audio_tmp).with_suffix(".normalized.wav")
        normalized.export(str(out_path), format="wav")
        print(f"[post_process] Normalized: {out_path}")
        return {"audioTmpPath": str(out_path)}
    except ImportError:
        print("[post_process] pydub not installed, skipping normalization (pip install pydub)")
        return {"audioTmpPath": audio_tmp}
    except Exception as e:
        print(f"[post_process] Normalization failed: {e} — using original")
        return {"audioTmpPath": audio_tmp}
