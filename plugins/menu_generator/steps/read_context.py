"""
Step: read_context
Reads game-design.md and architecture.md from .ggm/ to inject into LLM prompts.
"""

from pathlib import Path


def run(ctx: dict) -> dict:
    project_path = ctx["project_path"]
    ggm_dir = Path(project_path) / ".ggm"

    game_design = ""
    architecture = ""

    gd_file = ggm_dir / "game-design.md"
    if gd_file.exists():
        game_design = gd_file.read_text(encoding="utf-8")

    arch_file = ggm_dir / "architecture.md"
    if arch_file.exists():
        architecture = arch_file.read_text(encoding="utf-8")

    print(f"[read_context] game-design.md: {len(game_design)} chars")
    print(f"[read_context] architecture.md: {len(architecture)} chars")

    return {"gameDesign": game_design, "architecture": architecture}
