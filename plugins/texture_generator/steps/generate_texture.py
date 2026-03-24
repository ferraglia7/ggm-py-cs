"""
Step: generate_texture
Generates texture using ComfyUI/Flux (local) or Stability AI (cloud).
"""
import os
import base64
import requests
import json
from pathlib import Path


def run(ctx: dict) -> dict:
    inputs = ctx["inputs"]
    outputs = ctx["outputs"]
    project_path = ctx["project_path"]

    tex_name = inputs["name"]
    tex_type = inputs.get("textureType", "albedo")
    resolution = int(inputs.get("resolution", 1024))
    user_prompt = inputs.get("prompt", "")
    game_design = outputs.get("read_context", {}).get("gameDesign", "")

    # Build prompt
    if not user_prompt and game_design:
        user_prompt = f"{tex_name}, game texture, seamless tileable, based on: {game_design[:500]}"
    elif not user_prompt:
        user_prompt = f"{tex_name}, seamless tileable game texture, high quality PBR"

    tmp_dir = Path(project_path) / ".ggm" / "tmp" / tex_name
    tmp_dir.mkdir(parents=True, exist_ok=True)
    out_path = tmp_dir / f"{tex_name}.png"

    # Try ComfyUI first
    comfyui_host = os.environ.get("GGM_COMFYUI_HOST", "http://localhost:8090")
    try:
        health = requests.get(f"{comfyui_host}/health", timeout=2)
        if health.ok:
            print("[generate_texture] Using ComfyUI (local)")
            _comfyui_generate(user_prompt, resolution, out_path, comfyui_host)
            return {"textureTmpPath": str(out_path), "prompt": user_prompt}
    except Exception as e:
        print(f"[generate_texture] ComfyUI unavailable: {e}")

    # Try Flux
    flux_host = os.environ.get("GGM_FLUX_HOST", "http://localhost:8091")
    try:
        health = requests.get(f"{flux_host}/health", timeout=2)
        if health.ok:
            print("[generate_texture] Using Flux.1 (local)")
            res = requests.post(f"{flux_host}/generate",
                                json={"prompt": user_prompt, "width": resolution, "height": resolution},
                                timeout=120)
            res.raise_for_status()
            out_path.write_bytes(res.content)
            return {"textureTmpPath": str(out_path), "prompt": user_prompt}
    except Exception as e:
        print(f"[generate_texture] Flux unavailable: {e}")

    # Stability AI cloud
    stability_key = os.environ.get("GGM_STABILITY_KEY")
    if stability_key:
        print("[generate_texture] Using Stability AI (cloud)")
        res = requests.post(
            "https://api.stability.ai/v2beta/stable-image/generate/core",
            headers={"authorization": f"Bearer {stability_key}", "accept": "image/*"},
            files={"none": ""},
            data={"prompt": user_prompt, "output_format": "png"},
            timeout=60,
        )
        if res.ok:
            out_path.write_bytes(res.content)
            return {"textureTmpPath": str(out_path), "prompt": user_prompt}

    raise RuntimeError("No texture generation provider available. Start ComfyUI on port 8090 or set GGM_STABILITY_KEY.")


def _comfyui_generate(prompt: str, resolution: int, out_path: Path, host: str):
    """Simple ComfyUI API call (assumes a basic txt2img workflow is loaded)."""
    payload = {
        "prompt": {
            "3": {"class_type": "KSampler", "inputs": {
                "seed": 42, "steps": 20, "cfg": 7.0, "sampler_name": "euler",
                "scheduler": "normal", "denoise": 1.0,
                "model": ["4", 0], "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["5", 0]
            }},
            "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "v1-5-pruned-emaonly.safetensors"}},
            "5": {"class_type": "EmptyLatentImage", "inputs": {"width": resolution, "height": resolution, "batch_size": 1}},
            "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["4", 1]}},
            "7": {"class_type": "CLIPTextEncode", "inputs": {"text": "blurry, low quality, watermark", "clip": ["4", 1]}},
            "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
            "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "ggm_tex", "images": ["8", 0]}}
        }
    }
    res = requests.post(f"{host}/prompt", json=payload, timeout=120)
    res.raise_for_status()
    prompt_id = res.json().get("prompt_id")
    # Poll for result
    import time
    for _ in range(60):
        time.sleep(2)
        history = requests.get(f"{host}/history/{prompt_id}", timeout=10).json()
        if prompt_id in history:
            outputs = history[prompt_id].get("outputs", {})
            for node_out in outputs.values():
                images = node_out.get("images", [])
                if images:
                    img_filename = images[0]["filename"]
                    img_res = requests.get(f"{host}/view?filename={img_filename}", timeout=30)
                    out_path.write_bytes(img_res.content)
                    return
    raise RuntimeError("ComfyUI generation timed out")
