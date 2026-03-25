"""
Step: generate_cs
Generates C# MonoBehaviour controller for the menu using an LLM.
"""

import os
import re
import requests
from pathlib import Path


CS_SYSTEM = """You are a Unity C# expert. Generate a clean MonoBehaviour controller for a Unity UI Toolkit menu.

Rules:
- Use Unity UI Toolkit (UIDocument, VisualElement, Button.clicked)
- Use the namespace and manager singletons from architecture.md
- Wire up all buttons with proper callbacks (e.g. NewGame → GameStateManager.Instance.StartNewGame())
- Use [RequireComponent(typeof(UIDocument))]
- Output ONLY the C# code, no explanation, no markdown fences
"""


def run(ctx: dict) -> dict:
    inputs = ctx["inputs"]
    outputs = ctx["outputs"]
    project_path = ctx["project_path"]

    menu_name = inputs["name"]
    menu_type = inputs.get("menuType", "MainMenu")
    game_design = outputs.get("read_context", {}).get("gameDesign", "")
    architecture = outputs.get("read_context", {}).get("architecture", "")
    uxml_content = outputs.get("generate_layout", {}).get("uxmlContent", "")

    prompt = f"""Create a C# MonoBehaviour controller for: {menu_name} ({menu_type})

UXML layout (reference this to find button names and element names):
{uxml_content[:2000] if uxml_content else '(not available — use standard element names)'}

Architecture context (for namespace and manager usage):
{architecture[:1500] if architecture else '(not available)'}

Game design context:
{game_design[:1000] if game_design else '(not available)'}

Generate the C# controller."""

    cs_content = _llm_call(CS_SYSTEM, prompt)
    cs_content = re.sub(r"```(?:csharp|cs|c#)?\s*\n?", "", cs_content, flags=re.IGNORECASE)
    cs_content = re.sub(r"\n?```\s*$", "", cs_content).strip()

    tmp_dir = Path(project_path) / ".ggm" / "tmp" / menu_name
    tmp_dir.mkdir(parents=True, exist_ok=True)
    cs_path = tmp_dir / f"{menu_name}Controller.cs"
    cs_path.write_text(cs_content, encoding="utf-8")
    print(f"[generate_cs] C# saved: {cs_path}")

    return {"csContent": cs_content, "csTmpPath": str(cs_path)}


def _llm_call(system: str, prompt: str) -> str:
    claude_key = os.environ.get("GGM_CLAUDE_KEY")
    gemini_key = os.environ.get("GGM_GEMINI_KEY")

    if claude_key:
        try:
            res = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": claude_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
                json={"model": "claude-sonnet-4-6", "max_tokens": 3000, "system": system,
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=30,
            )
            if res.ok:
                return res.json()["content"][0]["text"]
        except Exception as e:
            print(f"[generate_cs] Claude failed: {e}")

    if gemini_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
            res = requests.post(url, json={
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"parts": [{"text": prompt}]}]
            }, timeout=30)
            if res.ok:
                return res.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            print(f"[generate_cs] Gemini failed: {e}")

    try:
        res = requests.post("http://localhost:11434/api/chat", json={
            "model": "qwen2.5-coder:7b",
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "stream": False,
        }, timeout=90)
        if res.ok:
            return res.json()["message"]["content"]
    except Exception as e:
        print(f"[generate_cs] Ollama failed: {e}")

    raise RuntimeError("No LLM provider available for C# generation")
