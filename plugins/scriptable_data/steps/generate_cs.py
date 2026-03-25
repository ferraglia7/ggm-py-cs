"""
generate_cs — emit a C# ScriptableObject class from the schema fields.
No LLM needed: deterministic codegen.
"""
import json


# C# type mapping from schema types to actual C# types
CS_TYPE_MAP = {
    "string":          "string",
    "int":             "int",
    "float":           "float",
    "bool":            "bool",
    "Color":           "Color",
    "Vector2":         "Vector2",
    "Vector3":         "Vector3",
    "Sprite":          "Sprite",
    "AudioClip":       "AudioClip",
    "GameObject":      "GameObject",
    "ScriptableObject":"ScriptableObject",
    "AnimationCurve":  "AnimationCurve",
}

DEFAULT_MAP = {
    "string":          '""',
    "int":             "0",
    "float":           "0f",
    "bool":            "false",
    "Color":           "Color.white",
    "Vector2":         "Vector2.zero",
    "Vector3":         "Vector3.zero",
    "Sprite":          "null",
    "AudioClip":       "null",
    "GameObject":      "null",
    "ScriptableObject":"null",
    "AnimationCurve":  "null",
}

NEEDS_UNITY_ENGINE = {"Color", "Vector2", "Vector3", "Sprite", "AudioClip", "GameObject", "AnimationCurve"}


def _field_to_cs(field: dict) -> tuple[str, str]:
    """Returns (declaration_line, tooltip_line)."""
    name      = field.get("name", "field")
    ftype     = field.get("type", "string")
    is_array  = field.get("isArray", False)
    default   = field.get("defaultValue", None)
    hint      = field.get("hint", "")

    cs_type = CS_TYPE_MAP.get(ftype, ftype)
    if is_array:
        cs_type = f"List<{cs_type}>"
        default_val = "new()"
    else:
        default_val = default if default is not None else DEFAULT_MAP.get(ftype, "null")

    tooltip = f'    [Tooltip("{hint}")]' if hint else ""
    decl    = f"    public {cs_type} {name} = {default_val};"
    return (decl, tooltip)


def run(ctx: dict) -> dict:
    inputs  = ctx["inputs"]
    outputs = ctx["outputs"]

    name      = inputs.get("name", "GeneratedSO")
    namespace = inputs.get("namespace", "RestaurantRoguelite.Data") or "RestaurantRoguelite.Data"
    fields    = outputs.get("design_schema", {}).get("fields", [])

    if not name.endswith("SO"):
        class_name = name + "SO"
    else:
        class_name = name

    # Determine required using directives
    used_unity_types = {f.get("type") for f in fields} & NEEDS_UNITY_ENGINE
    has_list = any(f.get("isArray") for f in fields)

    usings = ["using UnityEngine;"]
    if has_list:
        usings.insert(0, "using System.Collections.Generic;")

    field_lines = []
    for field in fields:
        decl, tooltip = _field_to_cs(field)
        if tooltip:
            field_lines.append(tooltip)
        field_lines.append(decl)
        field_lines.append("")

    # Remove trailing blank line
    while field_lines and field_lines[-1] == "":
        field_lines.pop()

    fields_block = "\n".join(field_lines)

    asset_menu_path = f"{namespace.replace('.', '/')}/{class_name}"

    cs_code = f"""{chr(10).join(usings)}

namespace {namespace}
{{
    [CreateAssetMenu(fileName = "New{class_name}", menuName = "{asset_menu_path}")]
    public class {class_name} : ScriptableObject
    {{
{fields_block}
    }}
}}
"""

    print(f"[generate_cs] Generated {class_name}.cs ({len(cs_code)} chars, {len(fields)} fields)")
    return {
        "code": cs_code,
        "className": class_name,
        "namespace": namespace,
        "fieldCount": len(fields),
    }
