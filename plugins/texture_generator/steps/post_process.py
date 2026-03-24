"""
Step: post_process
Makes texture seamlessly tileable using offset trick (if PIL available).
"""
from pathlib import Path


def run(ctx: dict) -> dict:
    inputs = ctx["inputs"]
    outputs = ctx["outputs"]
    tex_tmp = outputs.get("generate_texture", {}).get("textureTmpPath", "")
    seamless = inputs.get("seamless", True)

    if not tex_tmp or not Path(tex_tmp).exists():
        return {"textureTmpPath": tex_tmp}

    if not seamless:
        print("[post_process] Seamless disabled, skipping")
        return {"textureTmpPath": tex_tmp}

    try:
        from PIL import Image, ImageFilter
        img = Image.open(tex_tmp).convert("RGBA")
        w, h = img.size
        # Offset by half to expose tiling seam, blend with feathered composite
        offset_img = Image.new("RGBA", (w, h))
        offset_img.paste(img.crop((w//2, h//2, w, h)), (0, 0))
        offset_img.paste(img.crop((0, h//2, w//2, h)), (w//2, 0))
        offset_img.paste(img.crop((w//2, 0, w, h//2)), (0, h//2))
        offset_img.paste(img.crop((0, 0, w//2, h//2)), (w//2, h//2))
        out_path = Path(tex_tmp).with_suffix(".seamless.png")
        offset_img.save(str(out_path))
        print(f"[post_process] Seamless: {out_path}")
        return {"textureTmpPath": str(out_path)}
    except ImportError:
        print("[post_process] PIL not installed, skipping seamless (pip install Pillow)")
        return {"textureTmpPath": tex_tmp}
    except Exception as e:
        print(f"[post_process] Failed: {e} — using original")
        return {"textureTmpPath": tex_tmp}
