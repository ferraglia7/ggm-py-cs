"""
design_structure — AI designs the conversation outline (beats + branches).
Outputs a JSON structure used by generate_dialogue as a blueprint.
"""
import json
import os
import re


SYSTEM = """\
You are a narrative designer for video games. Design a conversation outline.
Output a JSON object with this structure:
{
  "nodes": [
    { "id": "Start", "speaker": "NPC_NAME", "beat": "short description of what NPC says here" },
    { "id": "PlayerChoice1", "speaker": "Player", "beat": "player response option A" },
    ...
  ],
  "flow": [
    { "from": "Start", "to": ["PlayerChoice1", "PlayerChoice2"] },
    ...
  ]
}
Reply ONLY with valid JSON, no markdown, no explanation.
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
            "stream": False,
        }).encode()
        req = urllib.request.Request(f"{ollama_url}/api/chat", data=payload, method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.loads(resp.read())["message"]["content"]

    def try_claude():
        if not claude_key: raise RuntimeError("No Claude key")
        payload = json.dumps({
            "model": "claude-sonnet-4-6", "max_tokens": 2048,
            "system": SYSTEM, "messages": [{"role": "user", "content": prompt}],
        }).encode()
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=payload, method="POST",
                                     headers={"Content-Type": "application/json",
                                              "x-api-key": claude_key, "anthropic-version": "2023-06-01"})
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.loads(resp.read())["content"][0]["text"]

    def try_gemini():
        if not gemini_key: raise RuntimeError("No Gemini key")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_key}"
        payload = json.dumps({"contents": [{"parts": [{"text": SYSTEM + "\n\n" + prompt}]}]}).encode()
        req = urllib.request.Request(url, data=payload, method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.loads(resp.read())["candidates"][0]["content"]["parts"][0]["text"]

    order = {
        "ollama": [("ollama", try_ollama)],
        "claude": [("claude", try_claude)],
        "gemini": [("gemini", try_gemini)],
    }.get(provider, [("ollama", try_ollama), ("claude", try_claude), ("gemini", try_gemini)])

    last_err = None
    for name, fn in order:
        try:
            print(f"[design_structure] Trying {name}...")
            result = fn()
            print(f"[design_structure] {name} OK")
            return result
        except Exception as e:
            print(f"[design_structure] {name} failed: {e}")
            last_err = e
    raise RuntimeError(f"All providers failed: {last_err}")


def run(ctx: dict) -> dict:
    inputs  = ctx["inputs"]
    outputs = ctx["outputs"]

    npc_name    = inputs.get("npcName", "NPC")
    description = inputs.get("description", "")
    mood        = inputs.get("mood", "neutral")
    branches    = inputs.get("branches", True)
    game_design = outputs.get("read_context", {}).get("gameDesign", "")[:2000]
    provider    = inputs.get("llmProvider", "auto")

    prompt = f"""Game context:
{game_design}

Design a conversation outline for this scene:
- NPC: {npc_name}
- Mood/tone: {mood}
- Scene: {description}
- Include player choices: {branches}

Keep it concise: 3-6 nodes total. Replace NPC_NAME with "{npc_name}" in all nodes."""

    raw = _call_llm(prompt, provider)
    raw = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()

    try:
        structure = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback minimal structure
        structure = {
            "nodes": [
                {"id": "Start", "speaker": npc_name, "beat": description},
                {"id": "End",   "speaker": npc_name, "beat": "Conversation ends"},
            ],
            "flow": [{"from": "Start", "to": ["End"]}],
        }
        print("[design_structure] JSON parse failed — using fallback structure")

    print(f"[design_structure] {len(structure.get('nodes', []))} nodes, {len(structure.get('flow', []))} transitions")
    return {"structure": structure}
