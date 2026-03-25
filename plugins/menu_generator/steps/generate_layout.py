"""
Step: generate_layout
Generates Unity UI Toolkit UXML layout for the menu using an LLM.
"""

import os
import re
import requests
import json


UXML_SYSTEM = """You are a Unity UI Toolkit expert. Generate a clean UXML layout file for a Unity game menu.

Rules:
- Use Unity UI Toolkit UXML format
- Use VisualElement, Button, Label with proper class names for styling
- Follow the game's visual style described in game-design.md
- Use BEM-like class names (e.g. main-menu__button, main-menu__title)
- Include a root container with the menu name as class
- Output ONLY the UXML XML, no explanation, no markdown fences
"""


def run(ctx: dict) -> dict:
    inputs = ctx["inputs"]
    outputs = ctx["outputs"]
    project_path = ctx["project_path"]

    menu_name = inputs["name"]
    menu_type = inputs.get("menuType", "MainMenu")
    visual_style = inputs.get("visualStyle", "")
    buttons = inputs.get("buttons", [])
    game_design = outputs.get("read_context", {}).get("gameDesign", "")
    architecture = outputs.get("read_context", {}).get("architecture", "")

    buttons_hint = ", ".join(buttons) if buttons else _default_buttons(menu_type)
    style_hint = visual_style or "(infer from game-design.md)"

    prompt = f"""Create a Unity UI Toolkit UXML file for: {menu_name} ({menu_type})

Buttons: {buttons_hint}
Visual style: {style_hint}

Game design context:
{game_design[:2000] if game_design else '(not available)'}

Architecture context (for class/namespace naming):
{architecture[:1000] if architecture else '(not available)'}

Generate the UXML file."""

    uxml_content = _llm_call(UXML_SYSTEM, prompt)
    uxml_content = re.sub(r"```(?:xml|uxml)?\s*\n?", "", uxml_content, flags=re.IGNORECASE)
    uxml_content = re.sub(r"\n?```\s*$", "", uxml_content).strip()

    # Save UXML to temp location in .ggm/
    from pathlib import Path
    tmp_dir = Path(project_path) / ".ggm" / "tmp" / menu_name
    tmp_dir.mkdir(parents=True, exist_ok=True)
    uxml_path = tmp_dir / f"{menu_name}.uxml"
    uxml_path.write_text(uxml_content, encoding="utf-8")
    print(f"[generate_layout] UXML saved: {uxml_path}")

    return {"uxmlContent": uxml_content, "uxmlTmpPath": str(uxml_path)}


def _default_buttons(menu_type: str) -> str:
    defaults = {
        "MainMenu": "New Game, Continue, Settings, Quit",
        "PauseMenu": "Resume, Settings, Main Menu, Quit",
        "HUD": "Health bar, Score, Mini-map",
        "Settings": "Audio volume, Graphics quality, Controls, Back",
    }
    return defaults.get(menu_type, "OK, Cancel, Back")


def _llm_call(system: str, prompt: str) -> str:
    claude_key = os.environ.get("GGM_CLAUDE_KEY")
    gemini_key = os.environ.get("GGM_GEMINI_KEY")

    if claude_key:
        try:
            res = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": claude_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
                json={"model": "claude-sonnet-4-6", "max_tokens": 2048, "system": system,
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=30,
            )
            if res.ok:
                return res.json()["content"][0]["text"]
        except Exception as e:
            print(f"[generate_layout] Claude failed: {e}")

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
            print(f"[generate_layout] Gemini failed: {e}")

    # Ollama fallback
    try:
        res = requests.post("http://localhost:11434/api/chat", json={
            "model": "llama3.1:8b",
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "stream": False,
        }, timeout=60)
        if res.ok:
            return res.json()["message"]["content"]
    except Exception as e:
        print(f"[generate_layout] Ollama failed: {e}")

    raise RuntimeError("No LLM provider available for layout generation")
