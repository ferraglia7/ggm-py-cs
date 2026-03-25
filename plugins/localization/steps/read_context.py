"""
read_context — read game-design.md and optionally an existing CSV for translate mode.
"""
from pathlib import Path


def run(ctx: dict) -> dict:
    project_path = ctx["project_path"]
    inputs       = ctx["inputs"]
    ggm          = Path(project_path) / ".ggm"

    game_design = ""
    gd_path = ggm / "game-design.md"
    if gd_path.exists():
        game_design = gd_path.read_text(encoding="utf-8")
        print(f"[read_context] Loaded game-design.md ({len(game_design)} chars)")

    existing_csv = ""
    csv_rel = inputs.get("existingCsv", "").strip()
    if csv_rel:
        csv_path = Path(project_path) / Path(csv_rel)
        if csv_path.exists():
            existing_csv = csv_path.read_text(encoding="utf-8")
            print(f"[read_context] Loaded existing CSV ({len(existing_csv)} chars)")
        else:
            print(f"[read_context] Existing CSV not found: {csv_rel}")

    return {"gameDesign": game_design, "existingCsv": existing_csv}
