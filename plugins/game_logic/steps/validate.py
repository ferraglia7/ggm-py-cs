"""
validate — lightweight syntax check on the generated C# code.
Checks for: balanced braces, required namespace declaration,
base class presence, common Unity anti-patterns.

This step is optional: errors are warnings, not hard failures.
"""
import re


def run(ctx: dict) -> dict:
    outputs = ctx["outputs"]
    gen     = outputs.get("generate_code", {})
    code    = gen.get("code", "")

    warnings = []
    errors   = []

    if not code:
        errors.append("generate_code produced no code")
        return {"valid": False, "errors": errors, "warnings": warnings}

    # Brace balance
    opens  = code.count("{")
    closes = code.count("}")
    if opens != closes:
        errors.append(f"Unbalanced braces: {opens} open, {closes} close")

    # Namespace present
    if "namespace " not in code:
        warnings.append("No namespace declaration found")

    # Class declaration
    if "class " not in code:
        errors.append("No class declaration found")

    # Old Unity APIs
    for old, new in [
        ("GetComponent<Rigidbody>().velocity", "linearVelocity"),
        (".drag ", ".linearDamping "),
        ("Input.GetKey", "New Input System"),
    ]:
        if old in code:
            warnings.append(f"Possible deprecated API: '{old}' → consider '{new}'")

    # Debug.Log without namespace
    if re.search(r'(?<!UnityEngine\.)Debug\.Log', code):
        warnings.append("Debug.Log without UnityEngine. prefix (may shadow custom Debug)")

    valid = len(errors) == 0

    if warnings:
        for w in warnings:
            print(f"[validate] WARN: {w}")
    if errors:
        for e in errors:
            print(f"[validate] ERROR: {e}")
    if valid:
        print(f"[validate] OK ({len(code)} chars)")

    return {"valid": valid, "errors": errors, "warnings": warnings}
