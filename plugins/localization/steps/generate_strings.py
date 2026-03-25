"""
generate_strings — generate source-language string table with AI.

Mode: generate → AI writes strings from game context + scope
Mode: translate → pass-through (strings come from existingCsv)
Mode: extract   → scan C# files for quoted strings (heuristic)

Output format: list of {key, value} for the source language
"""
import json
import os
import re


SYSTEM_GENERATE = """\
You are a game localisation expert. Generate a Unity string table as a JSON array.
Each entry: {"key": "UNIQUE_KEY", "value": "string in source language"}

Key naming: SCREAMING_SNAKE_CASE, prefixed by category (e.g. UI_START_GAME, MENU_SETTINGS).
Values: natural, polished game text appropriate for the tone described.

Reply ONLY with a JSON array, no markdown, no explanation.
"""


def _call_llm(prompt: str) -> str:
    import urllib.request

    ollama_url   = os.environ.get("GGM_OLLAMA_URL", "http://localhost:11434")
    ollama_model = os.environ.get("GGM_OLLAMA_MODEL", "llama3.2:3b")
    claude_key   = os.environ.get("GGM_CLAUDE_KEY", "")
    gemini_key   = os.environ.get("GGM_GEMINI_KEY", "")

    # 1. Ollama
    try:
        payload = json.dumps({
            "model": ollama_model,
            "messages": [
                {"role": "system", "content": SYSTEM_GENERATE},
                {"role": "user",   "content": prompt},
            ],
            "stream": False,
        }).encode()
        req = urllib.request.Request(f"{ollama_url}/api/chat",
                                     data=payload, method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())["message"]["content"]
    except Exception as e:
        print(f"[generate_strings] Ollama unavailable: {e}")

    # 2. Claude
    if claude_key:
        try:
            payload = json.dumps({
                "model": "claude-sonnet-4-6",
                "max_tokens": 2048,
                "system": SYSTEM_GENERATE,
                "messages": [{"role": "user", "content": prompt}],
            }).encode()
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=payload, method="POST",
                headers={"Content-Type": "application/json",
                         "x-api-key": claude_key,
                         "anthropic-version": "2023-06-01"},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read())["content"][0]["text"]
        except Exception as e:
            print(f"[generate_strings] Claude failed: {e}")

    # 3. Gemini
    if gemini_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_key}"
            payload = json.dumps({
                "contents": [{"parts": [{"text": SYSTEM_GENERATE + "\n\n" + prompt}]}],
            }).encode()
            req = urllib.request.Request(url, data=payload, method="POST",
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read())["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            print(f"[generate_strings] Gemini failed: {e}")

    raise RuntimeError("No LLM provider available")


def _extract_from_cs(project_path: str) -> list[dict]:
    """Heuristic extraction: find quoted string literals in C# UI code."""
    root = Path(project_path) / "Assets" / "SourceFiles" / "Scripts"
    entries = []
    seen = set()
    if not root.exists():
        return entries

    string_re = re.compile(r'"([A-Z][^"]{3,60})"')
    for f in list(root.rglob("*.cs"))[:50]:
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
            for m in string_re.finditer(text):
                s = m.group(1)
                if s not in seen:
                    seen.add(s)
                    key = re.sub(r'\W+', '_', s).upper()[:60]
                    entries.append({"key": key, "value": s})
        except Exception:
            pass
    return entries[:200]


from pathlib import Path


def run(ctx: dict) -> dict:
    inputs  = ctx["inputs"]
    outputs = ctx["outputs"]

    mode     = inputs.get("mode", "generate")
    context  = outputs.get("read_context", {})
    existing = context.get("existingCsv", "")

    if mode == "translate" and existing:
        # Parse existing CSV → list of {key, value}
        lines = existing.splitlines()
        entries = []
        for line in lines[1:]:  # skip header
            parts = line.split(",", 2)
            if len(parts) >= 2:
                entries.append({"key": parts[0].strip(), "value": parts[1].strip('"')})
        print(f"[generate_strings] Translate mode — loaded {len(entries)} strings from CSV")
        return {"entries": entries, "mode": mode}

    if mode == "extract":
        project_path = ctx["project_path"]
        entries = _extract_from_cs(project_path)
        print(f"[generate_strings] Extract mode — found {len(entries)} candidate strings")
        return {"entries": entries, "mode": mode}

    # Generate mode
    game_design = context.get("gameDesign", "")[:2500]
    scope       = inputs.get("tableScope", inputs.get("name", "UI"))
    src_lang    = inputs.get("sourceLanguage", "en")

    prompt = f"""Game context:
{game_design}

Generate a string table for the "{scope}" category of this game.
Source language: {src_lang}
Generate 20-40 strings covering all UI text, labels, buttons, messages for this category."""

    print(f"[generate_strings] Asking LLM to generate strings for scope '{scope}'")
    raw = _call_llm(prompt)
    raw = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
    try:
        entries = json.loads(raw)
        if not isinstance(entries, list):
            raise ValueError(f"Expected JSON array, got {type(entries).__name__}")
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[generate_strings] JSON parse failed ({e}), using fallback entries")
        prefix = scope.upper().replace(" ", "_")
        entries = [{"key": f"{prefix}_PLACEHOLDER_{i}", "value": f"[{scope} {i}]"} for i in range(1, 4)]
    print(f"[generate_strings] Generated {len(entries)} strings")
    return {"entries": entries, "mode": mode}
