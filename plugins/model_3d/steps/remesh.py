"""
Step: remesh (optional)
Optimizes polygon count via Meshy remesh API.
Skipped gracefully if provider doesn't support it.
"""

import os
import requests
import time
import json


def run(ctx: dict) -> dict:
    outputs = ctx["outputs"]
    gen_output = outputs.get("generate_3d", {})
    provider = gen_output.get("provider")
    task_id = gen_output.get("taskId")

    if provider != "meshy" or not task_id:
        print("[remesh] Skipping — only supported for Meshy provider")
        return {"skipped": True}

    meshy_key = os.environ.get("GGM_MESHY_KEY")
    if not meshy_key:
        print("[remesh] Skipping — no Meshy API key")
        return {"skipped": True}

    print("[remesh] Requesting remesh at 30k triangles...")
    res = requests.post(
        f"https://api.meshy.ai/web/v2/tasks/{task_id}/remesh",
        headers={"Authorization": f"Bearer {meshy_key}"},
        json={"topology": "triangle", "targetPolycount": 30000, "decimationMode": 0},
        timeout=30,
    )
    if res.status_code not in (200, 201, 202):
        print(f"[remesh] Skipping — remesh request failed {res.status_code}")
        return {"skipped": True}

    remesh_id = res.json().get("result") or res.json().get("id") or res.json().get("task_id")
    if not remesh_id:
        remesh_id = task_id  # some versions return the same ID

    remesh_data = _poll_remesh(f"https://api.meshy.ai/web/v2/tasks/{remesh_id}", meshy_key)
    return {"remeshData": remesh_data, "skipped": False}


def _poll_remesh(endpoint: str, api_key: str, interval: int = 10) -> dict:
    print("[remesh] Waiting...")
    while True:
        res = requests.get(endpoint, headers={"Authorization": f"Bearer {api_key}"}, timeout=30)
        data = res.json()
        if isinstance(data, list):
            data = data[-1]
        if "result" in data and isinstance(data["result"], dict):
            data = data["result"]
        status = data.get("status", "UNKNOWN")
        progress = data.get("progress", "")
        print(f"[remesh] {status} {f'({progress}%)' if progress else ''}")
        if status == "SUCCEEDED":
            return data
        if status in ("FAILED", "EXPIRED"):
            print(f"[remesh] Failed: {data} — continuing without remesh")
            return {}
        time.sleep(interval)
