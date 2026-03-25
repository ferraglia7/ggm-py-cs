"""
read_context — read game-design.md and architecture.md from .ggm/
Also scans existing C# files for interface/manager signatures to give LLM better context.
"""
import os
from pathlib import Path


MAX_CS_SNIPPETS = 6
MAX_SNIPPET_LINES = 30


def _extract_signatures(cs_path: Path) -> str:
    """Extract class/interface declarations and public members (no method bodies)."""
    lines = cs_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    out = []
    depth = 0
    for line in lines[:200]:
        stripped = line.strip()
        if any(kw in stripped for kw in ("class ", "interface ", "public ", "namespace ")):
            out.append(line)
        depth += stripped.count("{") - stripped.count("}")
        if len(out) >= MAX_SNIPPET_LINES:
            break
    return "\n".join(out)


def run(ctx: dict) -> dict:
    project_path = ctx["project_path"]
    ggm = Path(project_path) / ".ggm"

    game_design = ""
    architecture = ""

    gd_path = ggm / "game-design.md"
    ar_path = ggm / "architecture.md"

    if gd_path.exists():
        game_design = gd_path.read_text(encoding="utf-8")
        print(f"[read_context] Loaded game-design.md ({len(game_design)} chars)")
    if ar_path.exists():
        architecture = ar_path.read_text(encoding="utf-8")
        print(f"[read_context] Loaded architecture.md ({len(architecture)} chars)")

    # Scan for manager/system signatures
    cs_root = Path(project_path) / "Assets" / "SourceFiles" / "Scripts"
    snippets: list[str] = []
    if cs_root.exists():
        candidates = list(cs_root.rglob("*.cs"))
        # Prioritise Managers/ and Systems/
        candidates.sort(key=lambda p: (
            0 if "Managers" in p.parts else
            1 if "Systems" in p.parts else 2
        ))
        for f in candidates[:MAX_CS_SNIPPETS]:
            sig = _extract_signatures(f)
            if sig:
                snippets.append(f"// {f.relative_to(Path(project_path))}\n{sig}")

    cs_context = "\n\n".join(snippets)
    print(f"[read_context] Collected {len(snippets)} C# signature snippets")

    return {
        "gameDesign": game_design,
        "architecture": architecture,
        "csContext": cs_context,
    }
