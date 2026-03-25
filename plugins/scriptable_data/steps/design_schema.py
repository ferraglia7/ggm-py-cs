"""
design_schema — if no fields provided, ask the LLM to design the ScriptableObject schema
based on name, description, and game context.

Expected output: list of {name, type, defaultValue, hint, isArray}
"""
import json
import os
import re


FIELD_TYPES = [
    "string", "int", "float", "bool",
    "Color", "Vector2", "Vector3", "Sprite", "AudioClip",
    "GameObject", "ScriptableObject", "AnimationCurve",
]

SYSTEM_PROMPT = """\
You are a Unity C# architect. You design ScriptableObject schemas for Unity games.
Given a ScriptableObject name, description, and game context, output a JSON array of fields.

Each field must have:
- "name": camelCase or PascalCase field name
- "type": one of the allowed Unity types
- "defaultValue": sensible default as a string ("0", "1.0f", "true", "\"\"", etc.)
- "hint": short tooltip shown in Inspector
- "isArray": true if this should be a List<type>

Allowed types: string, int, float, bool, Color, Vector2, Vector3, Sprite, AudioClip,
               GameObject, ScriptableObject, AnimationCurve

Reply ONLY with a JSON array, no markdown fences, no explanations.
"""


def _call_llm(prompt: str) -> str:
    """Call LLM: tries Ollama first, then Claude, then Gemini."""
    import urllib.request

    # 1. Try Ollama
    ollama_url = os.environ.get("GGM_OLLAMA_URL", "http://localhost:11434")
    ollama_model = os.environ.get("GGM_OLLAMA_MODEL", "qwen2.5-coder:7b")
    try:
        payload = json.dumps({
            "model": ollama_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            "stream": False,
        }).encode()
        req = urllib.request.Request(
            f"{ollama_url}/api/chat",
            data=payload, method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
            return data["message"]["content"]
    except Exception as e:
        print(f"[design_schema] Ollama unavailable ({e}), trying Claude")

    # 2. Try Claude
    claude_key = os.environ.get("GGM_CLAUDE_KEY", "")
    if claude_key:
        try:
            payload = json.dumps({
                "model": "claude-sonnet-4-6",
                "max_tokens": 1024,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": prompt}],
            }).encode()
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=payload, method="POST",
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": claude_key,
                    "anthropic-version": "2023-06-01",
                },
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
                return data["content"][0]["text"]
        except Exception as e:
            print(f"[design_schema] Claude failed ({e}), trying Gemini")

    # 3. Try Gemini
    gemini_key = os.environ.get("GGM_GEMINI_KEY", "")
    if gemini_key:
        try:
            model = "gemini-2.0-flash"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}"
            payload = json.dumps({
                "contents": [{"parts": [{"text": SYSTEM_PROMPT + "\n\n" + prompt}]}],
            }).encode()
            req = urllib.request.Request(url, data=payload, method="POST",
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
                return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            print(f"[design_schema] Gemini failed ({e})")

    raise RuntimeError("No LLM provider available for schema design")


def _fallback_fields(name: str, description: str) -> list:
    """Minimal fallback schema when LLM is unavailable or returns invalid JSON."""
    return [
        {"name": "displayName",  "type": "string", "defaultValue": '""',    "hint": f"Display name for this {name}",    "isArray": False},
        {"name": "description",  "type": "string", "defaultValue": '""',    "hint": description or "Description",       "isArray": False},
        {"name": "value",        "type": "float",  "defaultValue": "0.0f",  "hint": "Primary numeric value",            "isArray": False},
        {"name": "isEnabled",    "type": "bool",   "defaultValue": "true",  "hint": "Whether this entry is active",     "isArray": False},
    ]


def run(ctx: dict) -> dict:
    inputs  = ctx["inputs"]
    outputs = ctx["outputs"]

    # If caller already provided fields, validate and pass through
    raw_fields = inputs.get("fields")
    if raw_fields:
        if isinstance(raw_fields, str):
            raw_fields = json.loads(raw_fields)
        if isinstance(raw_fields, list) and len(raw_fields) > 0:
            print(f"[design_schema] Using provided fields ({len(raw_fields)} fields)")
            return {"fields": raw_fields, "aiDesigned": False}

    # Otherwise ask LLM
    name        = inputs.get("name", "UnknownSO")
    description = inputs.get("description", "")
    game_design = outputs.get("read_context", {}).get("gameDesign", "")

    context_snippet = game_design[:2000] if game_design else "(no game context)"

    prompt = f"""ScriptableObject name: {name}
Description: {description or "(none provided)"}

Game context (excerpt):
{context_snippet}

Design the fields for this ScriptableObject."""

    print(f"[design_schema] Asking LLM to design schema for '{name}'")
    try:
        raw = _call_llm(prompt)
    except RuntimeError as e:
        print(f"[design_schema] All LLM providers failed: {e}")
        print(f"[design_schema] Using fallback schema for '{name}'")
        return {"fields": _fallback_fields(name, description), "aiDesigned": False, "fallback": True}

    # Strip markdown fences if present
    raw = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()

    try:
        fields = json.loads(raw)
        if not isinstance(fields, list):
            raise ValueError(f"Expected JSON array, got {type(fields).__name__}")
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[design_schema] JSON parse failed ({e}), using fallback schema")
        return {"fields": _fallback_fields(name, description), "aiDesigned": False, "fallback": True}

    print(f"[design_schema] AI designed {len(fields)} fields")
    return {"fields": fields, "aiDesigned": True}
