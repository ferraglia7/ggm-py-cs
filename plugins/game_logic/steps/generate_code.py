"""
generate_code — use LLM to generate or patch a C# Unity script.

Provider priority:
  1. Ollama qwen2.5-coder (local, best for code)
  2. Claude claude-sonnet-4-6
  3. Gemini gemini-2.0-flash

Outputs: { code, diff, isNewFile, className }
"""
import difflib
import json
import os
import re


SYSTEM_NEW = """\
You are an expert Unity C# developer. Generate a complete, compilable C# script.
Follow these rules:
- Use Unity 6 APIs (linearVelocity not velocity, etc.)
- Use RestaurantRoguelite.* namespace conventions
- Subscribe to events in OnEnable, unsubscribe in OnDisable
- Use UnityEngine.Debug.Log() explicitly
- No using statements for UnityEngine (already global in Unity)
- Output ONLY the raw C# code, no markdown, no explanation
"""

SYSTEM_PATCH = """\
You are an expert Unity C# developer. Patch the existing C# script below.
Apply ONLY the changes described by the user.
Output ONLY the complete modified C# file — raw code, no markdown, no explanation.
"""


def _call_llm(system: str, prompt: str, provider: str = "auto") -> str:
    import urllib.request

    ollama_url   = os.environ.get("GGM_OLLAMA_URL", "http://localhost:11434")
    ollama_model = os.environ.get("GGM_OLLAMA_CODE_MODEL", "qwen2.5-coder:7b")
    claude_key   = os.environ.get("GGM_CLAUDE_KEY", "")
    gemini_key   = os.environ.get("GGM_GEMINI_KEY", "")

    def try_ollama():
        payload = json.dumps({
            "model": ollama_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": prompt},
            ],
            "stream": False,
            "options": {"num_predict": 4096},
        }).encode()
        req = urllib.request.Request(
            f"{ollama_url}/api/chat",
            data=payload, method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            return data["message"]["content"]

    def try_claude():
        if not claude_key:
            raise RuntimeError("No Claude key")
        payload = json.dumps({
            "model": "claude-sonnet-4-6",
            "max_tokens": 8192,
            "system": system,
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
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            return data["content"][0]["text"]

    def try_gemini():
        if not gemini_key:
            raise RuntimeError("No Gemini key")
        model = "gemini-2.0-flash"
        url   = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}"
        payload = json.dumps({
            "contents": [{"parts": [{"text": system + "\n\n" + prompt}]}],
            "generationConfig": {"maxOutputTokens": 8192},
        }).encode()
        req = urllib.request.Request(url, data=payload, method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            return data["candidates"][0]["content"]["parts"][0]["text"]

    order = {
        "auto":   [("ollama", try_ollama), ("claude", try_claude), ("gemini", try_gemini)],
        "ollama": [("ollama", try_ollama)],
        "claude": [("claude", try_claude)],
        "gemini": [("gemini", try_gemini)],
    }.get(provider, [("ollama", try_ollama), ("claude", try_claude), ("gemini", try_gemini)])

    last_err = None
    for name, fn in order:
        try:
            print(f"[generate_code] Trying {name}...")
            result = fn()
            print(f"[generate_code] {name} succeeded ({len(result)} chars)")
            return result
        except Exception as e:
            print(f"[generate_code] {name} failed: {e}")
            last_err = e

    raise RuntimeError(f"All LLM providers failed. Last error: {last_err}")


def _strip_fences(text: str) -> str:
    """Remove ```csharp / ``` fences if the LLM wrapped the output."""
    text = re.sub(r"^```(?:csharp|cs|c#)?\s*\n?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def run(ctx: dict) -> dict:
    inputs  = ctx["inputs"]
    outputs = ctx["outputs"]

    name        = inputs.get("name", "GeneratedScript")
    description = inputs.get("description", "")
    base_class  = inputs.get("baseClass", "MonoBehaviour")
    namespace   = inputs.get("namespace", "RestaurantRoguelite") or "RestaurantRoguelite"
    provider    = inputs.get("llmProvider", "auto")

    context     = outputs.get("read_context", {})
    existing    = outputs.get("read_existing", {})
    game_design = context.get("gameDesign", "")[:3000]
    architecture= context.get("architecture", "")[:2000]
    cs_context  = context.get("csContext", "")[:2000]
    existing_code = existing.get("existingCode", "")
    is_new_file = existing.get("isNewFile", True)

    if not name.endswith(".cs"):
        class_name = name
    else:
        class_name = name[:-3]

    is_patch = bool(existing_code) and not is_new_file

    if is_patch:
        system = SYSTEM_PATCH
        prompt = f"""Existing script:
```csharp
{existing_code}
```

Requested changes:
{description}

Additional context:
- Namespace: {namespace}
- Game design notes: {game_design[:800]}
- Architecture: {architecture[:600]}
- Existing project signatures: {cs_context[:600]}
"""
    else:
        system = SYSTEM_NEW
        prompt = f"""Script name: {class_name}
Base class: {base_class}
Namespace: {namespace}

Description:
{description}

Game design context:
{game_design[:1500]}

Architecture:
{architecture[:1000]}

Existing project signatures (for reference):
{cs_context[:800]}

Generate the complete {class_name}.cs file."""

    raw = _call_llm(system, prompt, provider)
    code = _strip_fences(raw)

    # Build unified diff if patching
    diff = ""
    if is_patch and existing_code:
        diff = "".join(difflib.unified_diff(
            existing_code.splitlines(keepends=True),
            code.splitlines(keepends=True),
            fromfile=f"a/{class_name}.cs",
            tofile=f"b/{class_name}.cs",
        ))

    print(f"[generate_code] {'Patch' if is_patch else 'New'} | {len(code)} chars" +
          (f" | {diff.count(chr(10))} diff lines" if diff else ""))

    return {
        "code": code,
        "diff": diff,
        "className": class_name,
        "isNewFile": is_new_file,
        "isPatch": is_patch,
    }
