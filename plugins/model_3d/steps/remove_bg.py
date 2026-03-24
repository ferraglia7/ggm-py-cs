"""
Step: remove_bg
Removes background from the source image.
Supports REMBG (local) and remove.bg (cloud API).
"""

import os
import requests
from pathlib import Path


def run(ctx: dict) -> dict:
    inputs = ctx["inputs"]
    image_path = inputs.get("imagePath")
    if not image_path:
        raise ValueError("remove_bg step requires inputs.imagePath")

    image_bytes = Path(image_path).read_bytes()

    # Check if REMBG is available (local, preferred)
    rembg_host = os.environ.get("GGM_REMBG_HOST", "http://localhost:8120")
    try:
        health = requests.get(f"{rembg_host}/health", timeout=2)
        if health.ok:
            print("[remove_bg] Using REMBG (local)")
            return _rembg(image_bytes, image_path, rembg_host)
    except Exception:
        pass

    # Fallback to remove.bg API
    api_key = os.environ.get("GGM_REMOVEBG_KEY")
    if api_key:
        print("[remove_bg] Using remove.bg (cloud)")
        return _removebg_api(image_bytes, image_path, api_key)

    raise RuntimeError("No background removal provider available. Start REMBG locally or set GGM_REMOVEBG_KEY.")


def _rembg(image_bytes: bytes, original_path: str, host: str) -> dict:
    response = requests.post(
        f"{host}/api/remove",
        files={"file": ("image.png", image_bytes, "image/png")},
        data={"model": "isnet-general-use"},
        timeout=30,
    )
    response.raise_for_status()
    out_path = _output_path(original_path)
    out_path.write_bytes(response.content)
    print(f"[remove_bg] Saved: {out_path}")
    return {"transparentImagePath": str(out_path)}


def _removebg_api(image_bytes: bytes, original_path: str, api_key: str) -> dict:
    response = requests.post(
        "https://api.remove.bg/v1.0/removebg",
        files={"image_file": ("image.png", image_bytes, "image/png")},
        data={"size": "auto"},
        headers={"X-Api-Key": api_key},
        timeout=30,
    )
    if response.status_code != 200:
        raise RuntimeError(f"remove.bg error {response.status_code}: {response.text}")
    out_path = _output_path(original_path)
    out_path.write_bytes(response.content)
    print(f"[remove_bg] Saved: {out_path}")
    return {"transparentImagePath": str(out_path)}


def _output_path(original_path: str) -> Path:
    p = Path(original_path)
    return p.parent / f"{p.stem}_nobg.png"
