"""
Recipe Pipeline
===============
word → Gemini image generation → remove.bg → [icon + Meshy image-to-3D + remesh] → Unity prefab

Usage:
    python pipeline.py Soda
    python pipeline.py          (will prompt for name)
"""

import os
import sys
import json
import time
import base64
import requests
from pathlib import Path

# ─── CONFIGURATION ────────────────────────────────────────────────────────────

GEMINI_API_KEY    = os.environ.get("GGM_GEMINI_KEY")    or "AIzaSyBumwpNBea2ADaCvEyWC6Dt587xy8cnkrU"
REMOVE_BG_API_KEY = os.environ.get("GGM_REMOVEBG_KEY")  or "xbqedDzHLAmxsF5zcuHLMt6j"
MESHY_API_KEY     = os.environ.get("GGM_MESHY_KEY")     or "msy_w3ezW1yAYJjbYkMB031BhW3RxLBqGwLTSfwE"

UNITY_ASSETS      = Path(os.environ.get("GGM_UNITY_ASSETS") or r"C:\Users\marco\Progetto\Assets")
RECIPES_PATH      = UNITY_ASSETS / "Prefabs" / "Recipes"
UI_IMAGES_PATH    = UNITY_ASSETS / "UI" / "Images"

RECIPE_TYPES = ["meat", "fish", "drink", "wheat", "vegetables"]
PLATE_MAP = {
    "meat":       "Plate_Meat",
    "fish":       "Plate_Fish",
    "drink":      "Plate_Drink",
    "wheat":      "Plate_Wheat",
    "vegetables": "Plate_Vegetable",
}

PROMPT_TEMPLATE = (
    "generate a pic of a {name}, game asset, 45-degree isometric view from northeast angle, "
    "single isolated object, centered composition, clean transparent background, realistic "
    "fantasy style, very very subtle mystic glow, detailed textures with painterly finish, "
    "soft ambient occlusion, muted color palette with occasional vibrant accents, AAA game "
    "quality, stylized realism, no additional objects, no environment, no characters, no pot, "
    "sharp focus, studio lighting, 56 ratio"
)

# ─── GEMINI ────────────────────────────────────────────────────────────────────

def gemini_generate_image(recipe_name: str) -> bytes:
    """Generate image via Gemini 2.0 Flash image generation."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = PROMPT_TEMPLATE.format(name=recipe_name)

    print(f"[Gemini] Generating image for '{recipe_name}'...")
    response = client.models.generate_content(
        model="gemini-3.1-flash-image-preview",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"]
        )
    )
    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            return base64.b64decode(part.inline_data.data)
    raise RuntimeError("Gemini did not return an image")


def gemini_classify_type(recipe_name: str) -> str:
    """Classify recipe into one of the known types."""
    from google import genai

    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = (
        f"Classify the food/drink item '{recipe_name}' into exactly one of these "
        f"categories: meat, fish, drink, wheat, vegetables.\n"
        f"Reply with only the single category word, nothing else."
    )
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    recipe_type = response.text.strip().lower()
    if recipe_type not in RECIPE_TYPES:
        print(f"[Gemini] Unknown type '{recipe_type}', defaulting to 'meat'. Fix in Unity if wrong.")
        return "meat"
    print(f"[Gemini] Type: {recipe_type} → {PLATE_MAP[recipe_type]}")
    return recipe_type

# ─── REMOVE.BG ─────────────────────────────────────────────────────────────────

def remove_background(image_bytes: bytes) -> bytes:
    """Remove background via remove.bg API."""
    print("[remove.bg] Removing background...")
    response = requests.post(
        "https://api.remove.bg/v1.0/removebg",
        files={"image_file": ("image.png", image_bytes, "image/png")},
        data={"size": "auto"},
        headers={"X-Api-Key": REMOVE_BG_API_KEY},
    )
    if response.status_code != 200:
        raise RuntimeError(f"remove.bg error {response.status_code}: {response.text}")
    return response.content

# ─── ICON ──────────────────────────────────────────────────────────────────────

def save_icon(image_bytes: bytes, recipe_name: str) -> str:
    """Save transparent PNG as 2D icon. Returns Unity-relative path."""
    UI_IMAGES_PATH.mkdir(parents=True, exist_ok=True)
    path = UI_IMAGES_PATH / f"{recipe_name}.png"
    path.write_bytes(image_bytes)
    print(f"[Icon] Saved: {path}")
    return f"Assets/UI/Images/{recipe_name}.png"

# ─── MESHY ─────────────────────────────────────────────────────────────────────

def _upload_image(image_bytes: bytes) -> str:
    """
    Upload image to catbox.moe and return public URL for Meshy.
    Free, no API key required, designed for automated use.
    """
    print("[Upload] Uploading image for Meshy...")
    response = requests.post(
        "https://catbox.moe/user/api.php",
        data={"reqtype": "fileupload"},
        files={"fileToUpload": ("image.png", image_bytes, "image/png")},
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
    )
    if response.status_code != 200:
        raise RuntimeError(f"Upload failed {response.status_code}: {response.text}")
    url = response.text.strip()
    if not url.startswith("http"):
        raise RuntimeError(f"Upload returned unexpected response: {response.text!r}")
    print(f"[Upload] URL: {url}")
    return url


def meshy_create_task(image_url: str) -> str:
    """Start Meshy image-to-3D task."""
    print("[Meshy] Creating image-to-3D task...")
    response = requests.post(
        "https://api.meshy.ai/v1/image-to-3d",
        headers={"Authorization": f"Bearer {MESHY_API_KEY}"},
        json={
            "image_url": image_url,
            "ai_model": "meshy-6",
        }
    )
    if response.status_code not in (200, 201, 202):
        raise RuntimeError(f"Meshy error {response.status_code}: {response.text}")
    task_id = response.json()["result"]
    print(f"[Meshy] Task ID: {task_id}")
    return task_id


def meshy_poll(endpoint: str, label: str = "Meshy", interval: int = 10) -> dict:
    """Generic poller for Meshy tasks."""
    print(f"[{label}] Waiting...")
    first = True
    while True:
        response = requests.get(
            endpoint,
            headers={"Authorization": f"Bearer {MESHY_API_KEY}"}
        )
        data = response.json()
        if first:
            print(f"[{label}] Raw response: {json.dumps(data)[:500]}")
            first = False
        # Some endpoints return a list (remesh)
        if isinstance(data, list):
            data = data[-1]
        # Some endpoints wrap result in {"code":"OK","result":{...}}
        if "result" in data and isinstance(data["result"], dict):
            data = data["result"]
        status   = data.get("status", "UNKNOWN")
        progress = data.get("progress", "")
        print(f"[{label}] {status} {f'({progress}%)' if progress else ''}")
        if status == "SUCCEEDED":
            return data
        if status in ("FAILED", "EXPIRED"):
            raise RuntimeError(f"{label} task failed: {data}")
        time.sleep(interval)


def meshy_remesh(task_id: str) -> dict:
    """Request remesh at 30k triangles and wait for result."""
    print("[Meshy] Requesting remesh at 30k triangles...")
    response = requests.post(
        f"https://api.meshy.ai/web/v2/tasks/{task_id}/remesh",
        headers={"Authorization": f"Bearer {MESHY_API_KEY}"},
        json={
            "topology": "triangle",
            "targetPolycount": 30000,
            "decimationMode": 0,
        }
    )
    if response.status_code not in (200, 201, 202):
        print(f"[Meshy] Remesh request returned {response.status_code} — skipping remesh step.")
        print(f"        Response: {response.text}")
        return None

    print(f"[Meshy] Remesh POST response: {response.text[:500]}")

    remesh_id = response.json().get("result") or response.json().get("id") or response.json().get("task_id")
    if remesh_id:
        return meshy_poll(
            f"https://api.meshy.ai/web/v2/tasks/{remesh_id}",
            label="Remesh"
        )
    else:
        return meshy_poll(
            f"https://api.meshy.ai/web/v2/tasks/{task_id}/remesh",
            label="Remesh"
        )


def _download(url: str, dest: Path):
    r = requests.get(url, stream=True)
    r.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)


def meshy_download_assets(task_data: dict, remesh_data: dict, recipe_name: str) -> dict:
    """
    Download FBX and textures from Meshy into the Unity project.
    Uses remesh FBX if available, falls back to original.
    """
    recipe_folder  = RECIPES_PATH / recipe_name
    source_folder  = recipe_folder / "Source"
    texture_folder = recipe_folder / "Textures"
    source_folder.mkdir(parents=True, exist_ok=True)
    texture_folder.mkdir(parents=True, exist_ok=True)

    # ── FBX ──────────────────────────────────────────────────────────────────
    # Prefer remeshed FBX
    fbx_url = None
    if remesh_data:
        fbx_url = (remesh_data.get("model_urls") or {}).get("fbx")
    if not fbx_url:
        fbx_url = task_data["model_urls"]["fbx"]

    fbx_path = source_folder / f"{recipe_name}.fbx"
    print(f"[Meshy] Downloading FBX...")
    _download(fbx_url, fbx_path)

    # ── TEXTURES ─────────────────────────────────────────────────────────────
    print(f"[Meshy] texture_urls raw: {json.dumps(task_data.get('texture_urls'))[:300]}")
    raw = task_data.get("texture_urls", [])
    tex_dict = raw[0] if (isinstance(raw, list) and raw) else raw

    texture_paths = {"base": "", "metallic": "", "normal": ""}

    if isinstance(tex_dict, dict):
        for key, url in tex_dict.items():
            if not url:
                continue
            filename = url.split("?")[0].split("/")[-1]
            dest = texture_folder / filename
            print(f"[Meshy] Downloading texture: {filename}")
            _download(url, dest)

            fn = filename.lower()
            # Identify by filename pattern (as user confirmed from Meshy output)
            if "texture_normal" in fn:
                texture_paths["normal"] = str(dest)
            elif "metallic" in fn and "roughness" not in fn:
                texture_paths["metallic"] = str(dest)
            elif "roughness" not in fn and "normal" not in fn and "metallic" not in fn \
                    and "occlusion" not in fn and "geometry" not in fn:
                texture_paths["base"] = str(dest)

    if not texture_paths["base"]:
        print("[WARNING] Base texture not identified — check Textures folder and update recipe_meta.json manually.")
    if not texture_paths["normal"]:
        print("[WARNING] Normal map not identified — check Textures folder and update recipe_meta.json manually.")

    return {
        "fbx":      str(fbx_path),
        "base":     texture_paths["base"],
        "metallic": texture_paths["metallic"],
        "normal":   texture_paths["normal"],
    }

# ─── METADATA ──────────────────────────────────────────────────────────────────

def _to_unity_path(abs_path: str) -> str:
    """Convert absolute path to Unity Assets/... relative path."""
    if not abs_path:
        return ""
    try:
        rel = Path(abs_path).relative_to(UNITY_ASSETS.parent)
        return str(rel).replace("\\", "/")
    except ValueError:
        return abs_path.replace("\\", "/")


def write_metadata(recipe_name: str, recipe_type: str, assets: dict, icon_path: str):
    """
    Write recipe_meta.json last — this is what triggers the Unity Editor script.
    """
    meta = {
        "recipe_name":     recipe_name,
        "recipe_type":     recipe_type,
        "plate_prefab":    PLATE_MAP.get(recipe_type, "Plate_Meat"),
        "fbx_path":        _to_unity_path(assets["fbx"]),
        "base_texture":    _to_unity_path(assets["base"]),
        "metallic_texture":_to_unity_path(assets["metallic"]),
        "normal_texture":  _to_unity_path(assets["normal"]),
        "icon_path":       icon_path,
    }
    meta_path = RECIPES_PATH / recipe_name / "recipe_meta.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"[Meta] Written: {meta_path}")
    print(f"[Meta] Contents: {json.dumps(meta, indent=2)}")

# ─── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    recipe_name = (sys.argv[1].strip() if len(sys.argv) > 1
                   else input("Recipe name: ").strip())
    if not recipe_name:
        print("Error: recipe name is empty.")
        sys.exit(1)

    image_path = sys.argv[2].strip() if len(sys.argv) > 2 else None

    print(f"\n{'='*50}")
    print(f"  Pipeline: {recipe_name}")
    print(f"{'='*50}\n")

    # 1. Get image — from file if provided, otherwise generate via Gemini API
    if image_path:
        print(f"[Image] Loading from file: {image_path}")
        image_bytes = Path(image_path).read_bytes()
    else:
        image_bytes = gemini_generate_image(recipe_name)

    # 2. Remove background
    transparent = remove_background(image_bytes)

    # 3. Save icon to Unity UI/Images
    icon_unity_path = save_icon(transparent, recipe_name)

    # 4. Classify recipe type (runs in parallel with Meshy waiting time conceptually)
    recipe_type = gemini_classify_type(recipe_name)

    # 5. Upload transparent image so Meshy can access it
    image_url = _upload_image(transparent)

    # 6. Create Meshy image-to-3D task
    task_id = meshy_create_task(image_url)

    # 7. Poll until complete
    task_data = meshy_poll(
        f"https://api.meshy.ai/v1/image-to-3d/{task_id}",
        label="Meshy 3D"
    )

    # 8. Remesh at 30k triangles
    remesh_data = meshy_remesh(task_id)

    # 9. Download FBX + textures into Unity project
    assets = meshy_download_assets(task_data, remesh_data, recipe_name)

    # 10. Write metadata — triggers Unity Editor script
    write_metadata(recipe_name, recipe_type, assets, icon_unity_path)

    print(f"\n{'='*50}")
    print(f"  Done! Switch to Unity — prefab will be created automatically.")
    print(f"  Prefab: Assets/Prefabs/Recipes/{recipe_name}/{recipe_name}.prefab")
    print(f"{'='*50}\n")

    # Emit file list for the frontend run tracker (must be last line on success)
    python_files = [
        _to_unity_path(assets["fbx"]),
        _to_unity_path(assets["base"]),
        _to_unity_path(assets["metallic"]),
        _to_unity_path(assets["normal"]),
        icon_unity_path,
        f"Assets/Prefabs/Recipes/{recipe_name}/recipe_meta.json",
    ]
    print(f"[FILES] {json.dumps([f for f in python_files if f])}")


if __name__ == "__main__":
    main()
