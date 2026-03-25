"""
slice — slice a sprite sheet into individual sprites using PIL.
Modes: none (pass through), grid (fixed cell size), auto (detect by alpha gaps).
Skips gracefully if PIL not installed or sliceMode=none.
"""
import json
import os
from pathlib import Path


def _slice_grid(img, cell_w: int, cell_h: int, output_dir: Path, stem: str) -> list[str]:
    """Slice image into fixed-size cells, skip fully transparent cells."""
    width, height = img.size
    paths = []
    idx = 0
    for y in range(0, height, cell_h):
        for x in range(0, width, cell_w):
            cell = img.crop((x, y, x + cell_w, y + cell_h))
            # Skip blank cells (all transparent)
            if cell.mode == "RGBA":
                extremes = cell.getextrema()
                if extremes[3][1] == 0:
                    continue
            out_path = output_dir / f"{stem}_{idx:04d}.png"
            cell.save(str(out_path))
            paths.append(str(out_path))
            idx += 1
    return paths


def _slice_auto(img, output_dir: Path, stem: str) -> list[str]:
    """Auto-detect sprite boundaries using alpha channel horizontal/vertical gaps."""
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    width, height = img.size
    import struct

    # Build column/row opacity masks
    col_has_content = [False] * width
    row_has_content = [False] * height

    pixels = img.load()
    for x in range(width):
        for y in range(height):
            if pixels[x, y][3] > 10:
                col_has_content[x] = True
                row_has_content[y] = True

    # Find bounding box (simple approach — treat whole image as one sprite if complex)
    if not any(col_has_content):
        return []

    left   = next(i for i, v in enumerate(col_has_content) if v)
    right  = width - next(i for i, v in enumerate(reversed(col_has_content)) if v)
    top    = next(i for i, v in enumerate(row_has_content) if v)
    bottom = height - next(i for i, v in enumerate(reversed(row_has_content)) if v)

    cropped = img.crop((left, top, right, bottom))
    out_path = output_dir / f"{stem}_auto.png"
    cropped.save(str(out_path))
    return [str(out_path)]


def run(ctx: dict) -> dict:
    inputs  = ctx["inputs"]
    outputs = ctx["outputs"]

    slice_mode = inputs.get("sliceMode", "none")
    image_path = outputs.get("remove_bg", {}).get("outputPath") or inputs.get("imagePath", "")

    if not image_path or not Path(image_path).exists():
        raise FileNotFoundError(f"Source image not found: {image_path}")

    if slice_mode == "none":
        print("[slice] Skipped — sliceMode is none")
        return {"outputPaths": [image_path], "sliceCount": 1, "sliced": False}

    try:
        from PIL import Image
    except ImportError:
        print("[slice] PIL not installed — skipping slice, using source image")
        return {"outputPaths": [image_path], "sliceCount": 1, "sliced": False}

    project_path = ctx["project_path"]
    tmp_dir = Path(project_path) / ".ggm" / "tmp" / "sprites"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(image_path).stem

    img = Image.open(image_path).convert("RGBA")

    if slice_mode == "grid":
        cell_w = int(inputs.get("cellWidth",  "64") or "64")
        cell_h = int(inputs.get("cellHeight", "64") or "64")
        paths  = _slice_grid(img, cell_w, cell_h, tmp_dir, stem)
        print(f"[slice] Grid slice → {len(paths)} sprites ({cell_w}×{cell_h})")
    else:  # auto
        paths = _slice_auto(img, tmp_dir, stem)
        print(f"[slice] Auto slice → {len(paths)} sprites")

    return {"outputPaths": paths, "sliceCount": len(paths), "sliced": True}
