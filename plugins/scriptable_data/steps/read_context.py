"""
read_context — read game-design.md and architecture.md from .ggm/
"""
from pathlib import Path


def run(ctx: dict) -> dict:
    project_path = ctx["project_path"]
    ggm = Path(project_path) / ".ggm"

    game_design  = ""
    architecture = ""

    gd_path = ggm / "game-design.md"
    ar_path = ggm / "architecture.md"

    if gd_path.exists():
        game_design = gd_path.read_text(encoding="utf-8")
        print(f"[read_context] Loaded game-design.md ({len(game_design)} chars)")
    else:
        print("[read_context] No game-design.md found, continuing without context")

    if ar_path.exists():
        architecture = ar_path.read_text(encoding="utf-8")
        print(f"[read_context] Loaded architecture.md ({len(architecture)} chars)")
    else:
        print("[read_context] No architecture.md found, continuing without context")

    return {"gameDesign": game_design, "architecture": architecture}
