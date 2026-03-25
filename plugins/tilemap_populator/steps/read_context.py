"""
read_context — load game-design.md for tilemap generation.
"""
from pathlib import Path


def run(ctx: dict) -> dict:
    project_path = ctx["project_path"]
    ggm = Path(project_path) / ".ggm"

    game_design = ""
    gd = ggm / "game-design.md"
    if gd.exists():
        game_design = gd.read_text(encoding="utf-8")
        print(f"[read_context] game-design.md ({len(game_design)} chars)")

    return {"gameDesign": game_design}
