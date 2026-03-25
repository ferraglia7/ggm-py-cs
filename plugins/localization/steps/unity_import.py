"""
unity_import — write CSV string tables compatible with Unity Localization package.
One CSV per language: Assets/Localization/{tableName}_{lang}.csv
Format: Key,{lang}
"""
import csv
import io
import json
from pathlib import Path


def run(ctx: dict) -> dict:
    project_path = ctx["project_path"]
    inputs       = ctx["inputs"]
    outputs      = ctx["outputs"]

    table_name   = inputs.get("name", "StringTable")
    translate_out= outputs.get("translate", {})
    translations = translate_out.get("translations", {})
    src_lang     = inputs.get("sourceLanguage", "en")

    # Fallback: if translate was skipped, use source entries directly
    if not translations:
        src_entries = outputs.get("generate_strings", {}).get("entries", [])
        translations = {src_lang: src_entries}

    if not translations:
        print("[unity_import] No strings to write")
        return {}

    loc_dir = Path(project_path) / "Assets" / "Localization"
    loc_dir.mkdir(parents=True, exist_ok=True)

    first_path = None
    all_langs  = []

    for lang, entries in translations.items():
        buf = io.StringIO()
        writer = csv.writer(buf, quoting=csv.QUOTE_ALL)
        writer.writerow(["Key", lang])
        for entry in entries:
            writer.writerow([entry.get("key", ""), entry.get("value", "")])

        filename = f"{table_name}_{lang}.csv"
        dest     = loc_dir / filename
        dest.write_text(buf.getvalue(), encoding="utf-8")
        unity_path = f"Assets/Localization/{filename}"
        all_langs.append(lang)
        if first_path is None:
            first_path = unity_path
        print(f"[unity_import] Wrote {unity_path} ({len(entries)} strings)")

    # Write a manifest so Unity editor script knows what to import
    manifest_path = loc_dir / f"{table_name}_manifest.json"
    manifest_path.write_text(json.dumps({
        "action":    "import_localization_tables",
        "tableName": table_name,
        "languages": all_langs,
        "csvPaths":  [f"Assets/Localization/{table_name}_{l}.csv" for l in all_langs],
    }, indent=2), encoding="utf-8")

    result = {
        "tablePath":   first_path or "",
        "stringCount": len(list(translations.values())[0]) if translations else 0,
        "languages":   all_langs,
    }
    print(f"[FILES] {json.dumps({'tablePath': result['tablePath']})}")
    return result
