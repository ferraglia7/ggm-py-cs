"""
optimize — optional step: resize images to power-of-two dimensions and compress PNGs.
Skips gracefully if PIL not installed.
"""
import math
from pathlib import Path


def _next_pow2(n: int) -> int:
    return 2 ** math.ceil(math.log2(n)) if n > 0 else 1


def run(ctx: dict) -> dict:
    outputs = ctx["outputs"]
    paths   = outputs.get("slice", {}).get("outputPaths", [])

    if not paths:
        print("[optimize] No paths from slice step — skipping")
        return {"outputPaths": paths}

    try:
        from PIL import Image
    except ImportError:
        print("[optimize] PIL not installed — skipping optimize")
        return {"outputPaths": paths}

    result_paths = []
    for p in paths:
        path = Path(p)
        if not path.exists():
            result_paths.append(p)
            continue

        img = Image.open(p).convert("RGBA")
        w, h = img.size
        pw, ph = _next_pow2(w), _next_pow2(h)

        if pw != w or ph != h:
            img = img.resize((pw, ph), Image.LANCZOS)
            img.save(str(path), optimize=True, compress_level=6)
            print(f"[optimize] Resized {path.name}: {w}×{h} → {pw}×{ph}")
        else:
            img.save(str(path), optimize=True, compress_level=6)
            print(f"[optimize] Compressed {path.name} ({w}×{h})")

        result_paths.append(str(path))

    return {"outputPaths": result_paths}
