"""Step: read_context — reads game-design.md to guide audio generation."""
from pathlib import Path

def run(ctx: dict) -> dict:
    project_path = ctx["project_path"]
    gd_file = Path(project_path) / ".ggm" / "game-design.md"
    game_design = gd_file.read_text(encoding="utf-8") if gd_file.exists() else ""
    print(f"[read_context] game-design.md: {len(game_design)} chars")
    return {"gameDesign": game_design}
