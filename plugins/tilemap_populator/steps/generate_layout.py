"""
generate_layout — AI generates a tile grid layout as a 2D JSON array.

Output: list of rows, each row is a list of tile name strings.
Example: [["Wall","Wall","Wall"], ["Wall","Floor","Wall"], ...]
"""
import json
import os
import re


SYSTEM = """\
You are a 2D game level designer. Generate a tilemap layout as a JSON 2D array.

Rules:
- Output ONLY a JSON array of arrays (rows of tile names)
- Each inner array is one row of tiles from top to bottom
- Use ONLY tile names from the provided vocabulary
- First and last rows + first and last columns must be "Wall" (border)
- Reply with raw JSON only, no markdown, no explanation
"""


def _call_llm(prompt: str, provider: str) -> str:
    import urllib.request

    ollama_url   = os.environ.get("GGM_OLLAMA_URL", "http://localhost:11434")
    ollama_model = os.environ.get("GGM_OLLAMA_MODEL", "llama3.1:8b")
    claude_key   = os.environ.get("GGM_CLAUDE_KEY", "")
    gemini_key   = os.environ.get("GGM_GEMINI_KEY", "")

    def try_ollama():
        payload = json.dumps({
            "model": ollama_model,
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
            "stream": False, "options": {"num_predict": 8192},
        }).encode()
        req = urllib.request.Request(f"{ollama_url}/api/chat", data=payload, method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())["message"]["content"]

    def try_gemini():
        if not gemini_key: raise RuntimeError("No Gemini key")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_key}"
        payload = json.dumps({"contents": [{"parts": [{"text": SYSTEM + "\n\n" + prompt}]}],
                              "generationConfig": {"maxOutputTokens": 8192}}).encode()
        req = urllib.request.Request(url, data=payload, method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())["candidates"][0]["content"]["parts"][0]["text"]

    def try_claude():
        if not claude_key: raise RuntimeError("No Claude key")
        payload = json.dumps({
            "model": "claude-sonnet-4-6", "max_tokens": 8192,
            "system": SYSTEM, "messages": [{"role": "user", "content": prompt}],
        }).encode()
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=payload, method="POST",
                                     headers={"Content-Type": "application/json",
                                              "x-api-key": claude_key, "anthropic-version": "2023-06-01"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())["content"][0]["text"]

    order = {
        "ollama": [("ollama", try_ollama)],
        "gemini": [("gemini", try_gemini)],
        "claude": [("claude", try_claude)],
    }.get(provider, [("ollama", try_ollama), ("gemini", try_gemini), ("claude", try_claude)])

    last_err = None
    for name, fn in order:
        try:
            print(f"[generate_layout] Trying {name}...")
            result = fn()
            print(f"[generate_layout] {name} OK")
            return result
        except Exception as e:
            print(f"[generate_layout] {name} failed: {e}")
            last_err = e
    raise RuntimeError(f"All providers failed: {last_err}")


def _make_fallback(width: int, height: int, tile_vocab: list[str]) -> list[list[str]]:
    """Generate a simple bordered room as fallback."""
    floor = tile_vocab[1] if len(tile_vocab) > 1 else tile_vocab[0]
    wall  = tile_vocab[0]
    grid  = []
    for y in range(height):
        row = []
        for x in range(width):
            row.append(wall if (x == 0 or x == width - 1 or y == 0 or y == height - 1) else floor)
        grid.append(row)
    return grid


def run(ctx: dict) -> dict:
    inputs  = ctx["inputs"]
    outputs = ctx["outputs"]

    name        = inputs.get("name", "Level")
    description = inputs.get("description", "")
    width       = int(inputs.get("width",  "20") or "20")
    height      = int(inputs.get("height", "15") or "15")
    tile_names  = inputs.get("tileNames", "Floor,Wall")
    provider    = inputs.get("llmProvider", "auto")
    game_design = outputs.get("read_context", {}).get("gameDesign", "")[:1000]

    # Parse tile vocabulary
    tile_vocab = [t.strip() for t in tile_names.split(",") if t.strip()] if tile_names else ["Floor", "Wall"]
    if not tile_vocab:
        tile_vocab = ["Floor", "Wall"]

    prompt = f"""Game context:
{game_design}

Generate a {width}×{height} tilemap for: {description}
Level name: {name}
Tile vocabulary (use ONLY these names): {tile_vocab}
Grid size: {width} columns × {height} rows
Output {height} rows, each with exactly {width} tile names."""

    raw = _call_llm(prompt, provider)
    raw = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()

    try:
        grid = json.loads(raw)
        if not isinstance(grid, list) or not isinstance(grid[0], list):
            raise ValueError("Not a 2D array")
        # Normalize to correct dimensions
        while len(grid) < height:
            grid.append(["Wall"] * width)
        grid = grid[:height]
        for i, row in enumerate(grid):
            while len(row) < width:
                row.append("Floor")
            grid[i] = row[:width]
    except Exception as e:
        print(f"[generate_layout] Parse failed ({e}), using fallback grid")
        grid = _make_fallback(width, height, tile_vocab)

    total_tiles = sum(1 for row in grid for cell in row if cell != "")
    print(f"[generate_layout] Grid {width}×{height} = {total_tiles} tiles")

    return {"grid": grid, "width": width, "height": height, "tileVocab": tile_vocab}
