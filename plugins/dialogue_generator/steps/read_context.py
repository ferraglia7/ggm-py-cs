"""
read_context — load game-design.md and architecture.md for dialogue generation.
"""
from pathlib import Path


def run(ctx: dict) -> dict:
    project_path = ctx["project_path"]
    ggm = Path(project_path) / ".ggm"

    game_design  = ""
    architecture = ""

    gd = ggm / "game-design.md"
    if gd.exists():
        game_design = gd.read_text(encoding="utf-8")
        print(f"[read_context] game-design.md ({len(game_design)} chars)")

    arch = ggm / "architecture.md"
    if arch.exists():
        architecture = arch.read_text(encoding="utf-8")
        print(f"[read_context] architecture.md ({len(architecture)} chars)")

    return {"gameDesign": game_design, "architecture": architecture}
