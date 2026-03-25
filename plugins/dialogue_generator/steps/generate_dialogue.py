"""
generate_dialogue — generate full Yarn Spinner or Ink dialogue from the structure blueprint.

Yarn Spinner format (.yarn):
  title: NodeName
  ---
  NPC: Line of dialogue
  -> Player choice A
      <<jump NodeA>>
  -> Player choice B
  ===

Ink format (.ink):
  === node_name ===
  NPC: Line of dialogue
  + Player choice A -> node_a
  + Player choice B -> node_b
"""
import json
import os
import re


SYSTEM_YARN = """\
You are an expert Yarn Spinner dialogue writer for Unity games.
Generate a complete, valid Yarn Spinner (.yarn) dialogue file.

Rules:
- Each node starts with: title: NodeName / ---
- Each node ends with: ===
- NPC lines: NPC_NAME: dialogue text
- Player choices: -> choice text (indented with 4 spaces after ->)
- Jumps: <<jump NodeName>>
- First node must be named "Start"
- Last node must have no outgoing jumps (conversation ends naturally)
- Output ONLY the raw .yarn content, no markdown fences, no explanation
"""

SYSTEM_INK = """\
You are an expert Ink dialogue writer for Unity games.
Generate a complete, valid Ink (.ink) dialogue file.

Rules:
- Each knot starts with: === knot_name ===
- NPC lines: NPC_NAME: dialogue text
- Player choices: + choice text -> knot_name
- First knot must be === Start ===
- End knots with -> END
- Output ONLY the raw .ink content, no markdown fences, no explanation
"""


def _call_llm(system: str, prompt: str, provider: str) -> str:
    import urllib.request

    ollama_url   = os.environ.get("GGM_OLLAMA_URL", "http://localhost:11434")
    ollama_model = os.environ.get("GGM_OLLAMA_MODEL", "llama3.1:8b")
    claude_key   = os.environ.get("GGM_CLAUDE_KEY", "")
    gemini_key   = os.environ.get("GGM_GEMINI_KEY", "")

    def try_ollama():
        payload = json.dumps({
            "model": ollama_model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "stream": False, "options": {"num_predict": 4096},
        }).encode()
        req = urllib.request.Request(f"{ollama_url}/api/chat", data=payload, method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())["message"]["content"]

    def try_claude():
        if not claude_key: raise RuntimeError("No Claude key")
        payload = json.dumps({
            "model": "claude-sonnet-4-6", "max_tokens": 4096,
            "system": system, "messages": [{"role": "user", "content": prompt}],
        }).encode()
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=payload, method="POST",
                                     headers={"Content-Type": "application/json",
                                              "x-api-key": claude_key, "anthropic-version": "2023-06-01"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())["content"][0]["text"]

    def try_gemini():
        if not gemini_key: raise RuntimeError("No Gemini key")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_key}"
        payload = json.dumps({"contents": [{"parts": [{"text": system + "\n\n" + prompt}]}],
                              "generationConfig": {"maxOutputTokens": 4096}}).encode()
        req = urllib.request.Request(url, data=payload, method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())["candidates"][0]["content"]["parts"][0]["text"]

    order = {
        "ollama": [("ollama", try_ollama)],
        "claude": [("claude", try_claude)],
        "gemini": [("gemini", try_gemini)],
    }.get(provider, [("ollama", try_ollama), ("claude", try_claude), ("gemini", try_gemini)])

    last_err = None
    for name, fn in order:
        try:
            print(f"[generate_dialogue] Trying {name}...")
            result = fn()
            print(f"[generate_dialogue] {name} OK ({len(result)} chars)")
            return result
        except Exception as e:
            print(f"[generate_dialogue] {name} failed: {e}")
            last_err = e
    raise RuntimeError(f"All providers failed: {last_err}")


def _strip_fences(text: str) -> str:
    text = re.sub(r"^```\w*\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def run(ctx: dict) -> dict:
    inputs  = ctx["inputs"]
    outputs = ctx["outputs"]

    fmt         = inputs.get("format", "yarn")
    npc_name    = inputs.get("npcName", "NPC")
    description = inputs.get("description", "")
    mood        = inputs.get("mood", "neutral")
    branches    = inputs.get("branches", True)
    provider    = inputs.get("llmProvider", "auto")

    game_design = outputs.get("read_context", {}).get("gameDesign", "")[:1500]
    structure   = outputs.get("design_structure", {}).get("structure", {})

    structure_str = json.dumps(structure, indent=2) if structure else "(no structure)"

    system = SYSTEM_YARN if fmt == "yarn" else SYSTEM_INK
    prompt = f"""Game: {game_design[:800]}

NPC name: {npc_name}
Mood: {mood}
Scene: {description}
Include player choices: {branches}

Conversation outline to follow:
{structure_str}

Write the full {'Yarn Spinner' if fmt == 'yarn' else 'Ink'} dialogue file."""

    raw = _call_llm(system, prompt, provider)
    content = _strip_fences(raw)

    # Count dialogue lines (non-empty, non-header lines)
    lines = [l for l in content.splitlines() if l.strip() and not l.startswith("title:") and l.strip() != "---" and l.strip() != "==="]
    print(f"[generate_dialogue] {len(lines)} dialogue lines, format={fmt}")

    return {"content": content, "lineCount": len(lines), "format": fmt}
