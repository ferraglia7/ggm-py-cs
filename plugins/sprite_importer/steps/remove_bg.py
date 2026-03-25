"""
remove_bg — remove background from sprite using REMBG local service or remove.bg API.
Skips if removeBg=false.
"""
import json
import os
import shutil
from pathlib import Path


def run(ctx: dict) -> dict:
    inputs       = ctx["inputs"]
    project_path = ctx["project_path"]

    if not inputs.get("removeBg", True):
        image_path = inputs.get("imagePath", "")
        print("[remove_bg] Skipped — removeBg is false")
        return {"outputPath": image_path, "skipped": True}

    image_path = inputs.get("imagePath", "")
    if not image_path or not Path(image_path).exists():
        raise FileNotFoundError(f"Source image not found: {image_path}")

    # Temp output path
    tmp_dir = Path(project_path) / ".ggm" / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    stem   = Path(image_path).stem
    output = tmp_dir / f"{stem}_nobg.png"

    # 1. Try REMBG local service (port 8120)
    rembg_url = os.environ.get("GGM_REMBG_URL", "http://localhost:8120")
    try:
        import urllib.request
        with open(image_path, "rb") as f:
            img_data = f.read()

        req = urllib.request.Request(
            f"{rembg_url}/api/remove",
            data=img_data, method="POST",
            headers={"Content-Type": "application/octet-stream"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            output.write_bytes(resp.read())
        print(f"[remove_bg] REMBG local → {output.name}")
        return {"outputPath": str(output), "provider": "rembg"}
    except Exception as e:
        print(f"[remove_bg] REMBG unavailable ({e}), trying remove.bg API")

    # 2. Try remove.bg API
    removebg_key = os.environ.get("GGM_REMOVEBG_KEY", "")
    if removebg_key:
        try:
            import urllib.request
            import urllib.parse

            with open(image_path, "rb") as f:
                img_data = f.read()

            boundary = "----GGMFormBoundary"
            body = (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="image_file"; filename="{Path(image_path).name}"\r\n'
                f"Content-Type: image/png\r\n\r\n"
            ).encode() + img_data + f"\r\n--{boundary}--\r\n".encode()

            req = urllib.request.Request(
                "https://api.remove.bg/v1.0/removebg",
                data=body, method="POST",
                headers={
                    "X-Api-Key": removebg_key,
                    "Content-Type": f"multipart/form-data; boundary={boundary}",
                },
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                output.write_bytes(resp.read())
            print(f"[remove_bg] remove.bg API → {output.name}")
            return {"outputPath": str(output), "provider": "removebg_api"}
        except Exception as e:
            print(f"[remove_bg] remove.bg API failed ({e}), using original image")

    # 3. Fallback: use original image as-is
    shutil.copy2(image_path, output)
    print(f"[remove_bg] No BG removal provider — using original image")
    return {"outputPath": str(output), "provider": "none"}
