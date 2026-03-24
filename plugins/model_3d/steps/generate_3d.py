"""
Step: generate_3d
Generates a 3D model from the transparent image.
Uses configured provider: meshy (cloud) or local (hunyuan3d2, sf3d, triposr, instantmesh, shape_e).
"""

import os
import requests
import base64
import json
import time


PROVIDER_PORTS = {
    "hunyuan3d2": 8080,
    "sf3d": 8081,
    "triposr": 8082,
    "instantmesh": 8083,
    "shape_e": 8084,
}


def run(ctx: dict) -> dict:
    inputs = ctx["inputs"]
    outputs = ctx["outputs"]

    # Get transparent image from previous step
    transparent_path = outputs.get("remove_bg", {}).get("transparentImagePath") or inputs.get("imagePath")
    if not transparent_path:
        raise ValueError("generate_3d requires a transparent image (run remove_bg first)")

    image_bytes = open(transparent_path, "rb").read()

    # Determine provider
    provider = os.environ.get("GGM_3D_PROVIDER", "meshy")

    # Try local provider first if configured
    if provider in PROVIDER_PORTS:
        port = PROVIDER_PORTS[provider]
        try:
            health = requests.get(f"http://localhost:{port}/health", timeout=2)
            if health.ok:
                print(f"[generate_3d] Using {provider} (local)")
                return _local_generate(image_bytes, provider, port)
        except Exception:
            print(f"[generate_3d] {provider} local unavailable, falling back to Meshy")

    # Fallback to Meshy
    meshy_key = os.environ.get("GGM_MESHY_KEY")
    if meshy_key:
        print("[generate_3d] Using Meshy (cloud)")
        return _meshy_generate(image_bytes, meshy_key)

    raise RuntimeError("No 3D generation provider available. Start a local provider or set GGM_MESHY_KEY.")


def _local_generate(image_bytes: bytes, provider: str, port: int) -> dict:
    b64 = base64.b64encode(image_bytes).decode()
    res = requests.post(f"http://localhost:{port}/generate", json={"image": b64}, timeout=300)
    res.raise_for_status()
    data = res.json()
    return {"taskId": data.get("task_id"), "provider": provider, "taskData": data}


def _meshy_generate(image_bytes: bytes, api_key: str) -> dict:
    # Upload to catbox.moe for public URL
    image_url = _upload_image(image_bytes)

    # Create task
    res = requests.post(
        "https://api.meshy.ai/v1/image-to-3d",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"image_url": image_url, "ai_model": "meshy-6"},
        timeout=30,
    )
    if res.status_code not in (200, 201, 202):
        raise RuntimeError(f"Meshy error {res.status_code}: {res.text}")
    task_id = res.json()["result"]
    print(f"[generate_3d] Meshy task: {task_id}")

    # Poll until done
    task_data = _meshy_poll(f"https://api.meshy.ai/v1/image-to-3d/{task_id}", api_key)
    return {"taskId": task_id, "provider": "meshy", "taskData": task_data, "imageUrl": image_url}


def _upload_image(image_bytes: bytes) -> str:
    res = requests.post(
        "https://catbox.moe/user/api.php",
        data={"reqtype": "fileupload"},
        files={"fileToUpload": ("image.png", image_bytes, "image/png")},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    res.raise_for_status()
    url = res.text.strip()
    if not url.startswith("http"):
        raise RuntimeError(f"Upload failed: {url}")
    return url


def _meshy_poll(endpoint: str, api_key: str, interval: int = 10) -> dict:
    print("[generate_3d] Waiting for Meshy...")
    first = True
    while True:
        res = requests.get(endpoint, headers={"Authorization": f"Bearer {api_key}"}, timeout=30)
        data = res.json()
        if first:
            print(f"[generate_3d] Response: {json.dumps(data)[:300]}")
            first = False
        if isinstance(data, list):
            data = data[-1]
        if "result" in data and isinstance(data["result"], dict):
            data = data["result"]
        status = data.get("status", "UNKNOWN")
        progress = data.get("progress", "")
        print(f"[generate_3d] {status} {f'({progress}%)' if progress else ''}")
        if status == "SUCCEEDED":
            return data
        if status in ("FAILED", "EXPIRED"):
            raise RuntimeError(f"Meshy task failed: {data}")
        time.sleep(interval)
