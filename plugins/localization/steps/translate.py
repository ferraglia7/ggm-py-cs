"""
translate — translate source strings into target languages using AI.
Batches strings to avoid token limits.
Skips if targetLanguages is empty.
"""
import json
import os
import re


SYSTEM_TRANSLATE = """\
You are a professional game translator. Translate the JSON string table entries.
Keep the same JSON structure. Translate ONLY the "value" fields.
Keep keys identical. Preserve placeholders like {0}, {name}, etc.
Reply ONLY with a JSON array, no markdown, no explanation.
"""

BATCH_SIZE = 20


def _call_llm(prompt: str) -> str:
    import urllib.request

    ollama_url  = os.environ.get("GGM_OLLAMA_URL", "http://localhost:11434")
    claude_key  = os.environ.get("GGM_CLAUDE_KEY", "")
    gemini_key  = os.environ.get("GGM_GEMINI_KEY", "")

    try:
        payload = json.dumps({
            "model": os.environ.get("GGM_OLLAMA_MODEL", "llama3.2:3b"),
            "messages": [
                {"role": "system", "content": SYSTEM_TRANSLATE},
                {"role": "user",   "content": prompt},
            ],
            "stream": False,
        }).encode()
        req = urllib.request.Request(f"{ollama_url}/api/chat",
                                     data=payload, method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.loads(resp.read())["message"]["content"]
    except Exception:
        pass

    if claude_key:
        try:
            payload = json.dumps({
                "model": "claude-sonnet-4-6",
                "max_tokens": 4096,
                "system": SYSTEM_TRANSLATE,
                "messages": [{"role": "user", "content": prompt}],
            }).encode()
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=payload, method="POST",
                headers={"Content-Type": "application/json",
                         "x-api-key": claude_key,
                         "anthropic-version": "2023-06-01"},
            )
            with urllib.request.urlopen(req, timeout=90) as resp:
                return json.loads(resp.read())["content"][0]["text"]
        except Exception as e:
            print(f"[translate] Claude failed: {e}")

    if gemini_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_key}"
            payload = json.dumps({
                "contents": [{"parts": [{"text": SYSTEM_TRANSLATE + "\n\n" + prompt}]}],
            }).encode()
            req = urllib.request.Request(url, data=payload, method="POST",
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=90) as resp:
                return json.loads(resp.read())["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            print(f"[translate] Gemini failed: {e}")

    raise RuntimeError("No LLM provider available for translation")


def _translate_batch(entries: list[dict], target_lang: str) -> list[dict]:
    prompt = f"""Translate to {target_lang}:
{json.dumps(entries, ensure_ascii=False, indent=2)}"""
    raw = _call_llm(prompt)
    raw = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
    return json.loads(raw)


def run(ctx: dict) -> dict:
    inputs  = ctx["inputs"]
    outputs = ctx["outputs"]

    target_langs_raw = inputs.get("targetLanguages", "").strip()
    if not target_langs_raw:
        print("[translate] No targetLanguages — skipping translation")
        return {"translations": {}, "skipped": True}

    target_langs = [l.strip() for l in target_langs_raw.split(",") if l.strip()]
    entries      = outputs.get("generate_strings", {}).get("entries", [])
    src_lang     = inputs.get("sourceLanguage", "en")

    if not entries:
        print("[translate] No source strings to translate")
        return {"translations": {}, "skipped": True}

    translations: dict[str, list[dict]] = {src_lang: entries}

    for lang in target_langs:
        print(f"[translate] Translating {len(entries)} strings → {lang}")
        all_translated = []
        for i in range(0, len(entries), BATCH_SIZE):
            batch = entries[i:i + BATCH_SIZE]
            try:
                translated = _translate_batch(batch, lang)
                all_translated.extend(translated)
                print(f"[translate]   Batch {i//BATCH_SIZE + 1} → {lang} ({len(translated)} strings)")
            except Exception as e:
                print(f"[translate]   Batch failed for {lang}: {e} — using source")
                all_translated.extend(batch)
        translations[lang] = all_translated

    return {
        "translations": translations,
        "languages": list(translations.keys()),
        "stringCount": len(entries),
    }
