"""
Step: generate_audio
Generates audio using local (MusicGen/AudioGen/Coqui) or cloud (ElevenLabs) provider.
"""
import os
import json
import requests
import base64
from pathlib import Path


def run(ctx: dict) -> dict:
    inputs = ctx["inputs"]
    outputs = ctx["outputs"]
    project_path = ctx["project_path"]

    audio_type = inputs.get("audioType", "music")
    track_name = inputs["name"]
    user_prompt = inputs.get("prompt", "")
    game_design = outputs.get("read_context", {}).get("gameDesign", "")

    # Build a rich prompt using game context
    if game_design and not user_prompt:
        # Let LLM derive a good prompt
        user_prompt = _derive_audio_prompt(track_name, audio_type, game_design)

    tmp_dir = Path(project_path) / ".ggm" / "tmp" / track_name
    tmp_dir.mkdir(parents=True, exist_ok=True)
    out_path = tmp_dir / f"{track_name}.wav"

    if audio_type == "music":
        _generate_music(user_prompt or track_name, out_path)
    elif audio_type == "sfx":
        _generate_sfx(user_prompt or track_name, out_path)
    elif audio_type in ("voice", "ambient"):
        _generate_tts(user_prompt or track_name, out_path)

    print(f"[generate_audio] Output: {out_path}")
    return {"audioTmpPath": str(out_path), "prompt": user_prompt}


def _generate_music(prompt: str, out_path: Path):
    musicgen_host = os.environ.get("GGM_MUSICGEN_HOST", "http://localhost:8100")
    try:
        health = requests.get(f"{musicgen_host}/health", timeout=2)
        if health.ok:
            print("[generate_audio] Using MusicGen (local)")
            res = requests.post(f"{musicgen_host}/generate", json={"prompt": prompt, "duration": 30}, timeout=300)
            res.raise_for_status()
            out_path.write_bytes(res.content)
            return
    except Exception as e:
        print(f"[generate_audio] MusicGen unavailable: {e}")
    raise RuntimeError("No music generation provider available. Start MusicGen on port 8100.")


def _generate_sfx(prompt: str, out_path: Path):
    audiogen_host = os.environ.get("GGM_AUDIOGEN_HOST", "http://localhost:8101")
    try:
        health = requests.get(f"{audiogen_host}/health", timeout=2)
        if health.ok:
            print("[generate_audio] Using AudioGen (local)")
            res = requests.post(f"{audiogen_host}/generate", json={"prompt": prompt}, timeout=120)
            res.raise_for_status()
            out_path.write_bytes(res.content)
            return
    except Exception as e:
        print(f"[generate_audio] AudioGen unavailable: {e}")

    elevenlabs_key = os.environ.get("GGM_ELEVENLABS_KEY")
    if elevenlabs_key:
        print("[generate_audio] Using ElevenLabs (cloud)")
        res = requests.post(
            "https://api.elevenlabs.io/v1/sound-generation",
            headers={"xi-api-key": elevenlabs_key, "Content-Type": "application/json"},
            json={"text": prompt, "duration_seconds": 3},
            timeout=30,
        )
        res.raise_for_status()
        out_path.write_bytes(res.content)
        return

    raise RuntimeError("No SFX provider available. Start AudioGen on port 8101 or set GGM_ELEVENLABS_KEY.")


def _generate_tts(text: str, out_path: Path):
    coqui_host = os.environ.get("GGM_COQUI_HOST", "http://localhost:8110")
    try:
        health = requests.get(f"{coqui_host}/health", timeout=2)
        if health.ok:
            print("[generate_audio] Using Coqui TTS (local)")
            res = requests.post(f"{coqui_host}/synthesize", json={"text": text}, timeout=60)
            res.raise_for_status()
            out_path.write_bytes(res.content)
            return
    except Exception as e:
        print(f"[generate_audio] Coqui unavailable: {e}")

    piper_host = os.environ.get("GGM_PIPER_HOST", "http://localhost:8111")
    try:
        health = requests.get(f"{piper_host}/health", timeout=2)
        if health.ok:
            print("[generate_audio] Using Piper TTS (local)")
            res = requests.post(f"{piper_host}/synthesize", json={"text": text}, timeout=30)
            res.raise_for_status()
            out_path.write_bytes(res.content)
            return
    except Exception as e:
        print(f"[generate_audio] Piper unavailable: {e}")

    raise RuntimeError("No TTS provider available. Start Coqui on port 8110 or Piper on 8111.")


def _derive_audio_prompt(name: str, audio_type: str, game_design: str) -> str:
    """Use LLM to generate a descriptive audio prompt from the game context."""
    claude_key = os.environ.get("GGM_CLAUDE_KEY")
    gemini_key = os.environ.get("GGM_GEMINI_KEY")
    prompt = (
        f"Based on this game design document, write a concise audio generation prompt "
        f"for a {audio_type} track named '{name}'. "
        f"Reply with only the prompt, 1-2 sentences max.\n\nGame design:\n{game_design[:1500]}"
    )
    if claude_key:
        try:
            res = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": claude_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
                json={"model": "claude-haiku-4-5-20251001", "max_tokens": 150,
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=15,
            )
            if res.ok:
                return res.json()["content"][0]["text"].strip()
        except Exception: pass
    if gemini_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
            res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=15)
            if res.ok:
                return res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception: pass
    return name  # fallback: just use the track name
