"""
Step: classify
Classifies the asset type from the image + name using an LLM.
Returns: assetType (weapon/character/prop/food/environment/...)
         and for recipe_3d compatibility: recipeCategory (meat/fish/drink/wheat/vegetables)
"""

import os
import json
import requests


ASSET_TYPES = ["weapon", "character", "prop", "food", "drink", "environment", "furniture", "container", "vehicle", "creature"]
RECIPE_CATEGORIES = ["meat", "fish", "drink", "wheat", "vegetables"]


def run(ctx: dict) -> dict:
    inputs = ctx["inputs"]
    name = inputs.get("name", "unknown")

    # Try LLM classification
    gemini_key = os.environ.get("GGM_GEMINI_KEY")
    claude_key = os.environ.get("GGM_CLAUDE_KEY")
    ollama_host = "http://localhost:11434"

    asset_type = _classify_with_llm(name, gemini_key, claude_key, ollama_host)
    print(f"[classify] Asset type: {asset_type}")

    # Also classify for recipe category (backward compat with recipe_3d / pipeline.py)
    recipe_cat = None
    if asset_type in ("food", "drink"):
        recipe_cat = _classify_recipe_category(name, gemini_key, claude_key, ollama_host)
        print(f"[classify] Recipe category: {recipe_cat}")

    return {"assetType": asset_type, "recipeCategory": recipe_cat}


def _classify_with_llm(name: str, gemini_key, claude_key, ollama_host) -> str:
    prompt = (
        f"Classify the game asset '{name}' into exactly one of these categories: "
        f"{', '.join(ASSET_TYPES)}.\n"
        f"Reply with only the single category word, nothing else."
    )
    result = _llm_call(prompt, gemini_key, claude_key, ollama_host)
    result = result.strip().lower()
    return result if result in ASSET_TYPES else "prop"


def _classify_recipe_category(name: str, gemini_key, claude_key, ollama_host) -> str:
    prompt = (
        f"Classify the food/drink '{name}' into exactly one of these categories: "
        f"{', '.join(RECIPE_CATEGORIES)}.\n"
        f"Reply with only the single category word, nothing else."
    )
    result = _llm_call(prompt, gemini_key, claude_key, ollama_host)
    result = result.strip().lower()
    return result if result in RECIPE_CATEGORIES else "meat"


def _llm_call(prompt: str, gemini_key, claude_key, ollama_host) -> str:
    # Try Gemini
    if gemini_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
            res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=10)
            if res.ok:
                return res.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            print(f"[classify] Gemini failed: {e}")

    # Try Claude
    if claude_key:
        try:
            res = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": claude_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
                json={"model": "claude-haiku-4-5-20251001", "max_tokens": 50, "messages": [{"role": "user", "content": prompt}]},
                timeout=10,
            )
            if res.ok:
                return res.json()["content"][0]["text"]
        except Exception as e:
            print(f"[classify] Claude failed: {e}")

    # Try Ollama
    try:
        res = requests.post(
            f"{ollama_host}/api/generate",
            json={"model": "llama3.1:8b", "prompt": prompt, "stream": False},
            timeout=15,
        )
        if res.ok:
            return res.json().get("response", "")
    except Exception as e:
        print(f"[classify] Ollama failed: {e}")

    return "prop"  # default fallback
