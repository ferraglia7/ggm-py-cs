"""
GGM Runner
==========
Generic plugin orchestrator.

Usage:
    python runner.py --plugin model_3d --project /path/to/unity --steps remove_bg,classify,generate_3d
    python runner.py --plugin model_3d --project /path/to/unity  # runs all steps
    python runner.py --plugin model_3d --project /path/to/unity --resume  # resumes from last partial session

The runner:
1. Reads plugins/{plugin_id}/manifest.json to know the steps
2. Loads .ggm/sessions/{session_id}.json for the session state (if any)
3. Runs only the requested/pending steps, in order
4. Updates session state after each step
5. Writes outputs to Unity project
"""

import argparse
import json
import os
import sys
import importlib
import uuid
from datetime import datetime
from pathlib import Path


def load_manifest(plugin_id: str) -> dict:
    manifest_path = Path(__file__).parent / "plugins" / plugin_id / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")
    with open(manifest_path) as f:
        return json.load(f)


def load_session(project_path: str, plugin_id: str, asset_name: str) -> dict | None:
    sessions_dir = Path(project_path) / ".ggm" / "sessions"
    # Session identity: pluginId + inputs.name
    for f in sessions_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            if data.get("pluginId") == plugin_id and data.get("inputs", {}).get("name") == asset_name:
                return data
        except Exception:
            pass
    return None


def save_session(project_path: str, session: dict):
    sessions_dir = Path(project_path) / ".ggm" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    session_file = sessions_dir / f"{session['id']}.json"
    session_file.write_text(json.dumps(session, indent=2))


def run_plugin(plugin_id: str, project_path: str, inputs: dict, steps: list[str] | None = None, resume: bool = False, run_id: str | None = None):
    """
    Orchestrate a plugin run.

    Args:
        plugin_id: e.g. "model_3d"
        project_path: absolute path to Unity project root
        inputs: plugin input parameters (e.g. {"name": "Sword", "imageId": "uuid"})
        steps: list of step IDs to run (None = all)
        resume: if True, skip already-completed steps from existing session
        run_id: external run ID from ggm-fe (for linking run ↔ session)
    """
    manifest = load_manifest(plugin_id)
    asset_name = inputs.get("name", "unknown")

    # Load or create session
    session = load_session(project_path, plugin_id, asset_name)
    if not session:
        session = {
            "id": str(uuid.uuid4()),
            "pluginId": plugin_id,
            "status": "running",
            "completedSteps": [],
            "pendingSteps": [],
            "failedStep": None,
            "stepOutputs": {},
            "inputs": inputs,
            "author": os.environ.get("GGM_USER", ""),
            "runId": run_id or str(uuid.uuid4()),
            "startedAt": datetime.utcnow().isoformat() + "Z",
            "lastActivityAt": datetime.utcnow().isoformat() + "Z",
        }

    # Update runId on resume
    if run_id:
        session["runId"] = run_id

    # Determine which steps to run
    all_steps = [s["id"] for s in manifest.get("steps", [])]
    target_steps = steps if steps else all_steps

    if resume:
        already_done = set(session.get("completedSteps", []))
        target_steps = [s for s in target_steps if s not in already_done]

    print(f"[Runner] Plugin: {plugin_id} | Asset: {asset_name} | Steps: {target_steps}")

    # Load the plugin module
    plugin_module_path = f"plugins.{plugin_id}.main"
    try:
        plugin_mod = importlib.import_module(plugin_module_path)
    except ImportError:
        # Fallback: try to import each step independently
        plugin_mod = None

    ctx = {
        "project_path": project_path,
        "inputs": inputs,
        "session": session,
        "manifest": manifest,
        "outputs": session.get("stepOutputs", {}),
    }

    for step_id in target_steps:
        print(f"[Runner] Step: {step_id}")
        session["lastActivityAt"] = datetime.utcnow().isoformat() + "Z"

        try:
            if plugin_mod and hasattr(plugin_mod, f"step_{step_id}"):
                # Plugin has a unified main.py with step functions
                step_fn = getattr(plugin_mod, f"step_{step_id}")
                result = step_fn(ctx)
            else:
                # Try per-step module: plugins/{plugin_id}/steps/{step_id}.py
                step_module_path = f"plugins.{plugin_id}.steps.{step_id}"
                step_mod = importlib.import_module(step_module_path)
                result = step_mod.run(ctx)

            ctx["outputs"][step_id] = result or {}
            session["stepOutputs"] = ctx["outputs"]
            if step_id not in session["completedSteps"]:
                session["completedSteps"].append(step_id)
            session["failedStep"] = None

        except Exception as e:
            print(f"[Runner] Step {step_id} FAILED: {e}", file=sys.stderr)
            session["failedStep"] = step_id
            session["status"] = "partial"
            save_session(project_path, session)
            raise

        save_session(project_path, session)

    # All steps done
    all_done = all(s in session["completedSteps"] for s in all_steps)
    session["status"] = "done" if all_done else "partial"
    save_session(project_path, session)
    print(f"[Runner] Done. Session status: {session['status']}")
    return session


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GGM Plugin Runner")
    parser.add_argument("--plugin",  required=True, help="Plugin ID (e.g. model_3d)")
    parser.add_argument("--project", required=True, help="Absolute path to Unity project root")
    parser.add_argument("--name",    required=True, help="Asset name (e.g. Sword)")
    parser.add_argument("--image",   help="Image path (for model_3d)")
    parser.add_argument("--steps",   help="Comma-separated step IDs to run (default: all)")
    parser.add_argument("--resume",  action="store_true", help="Skip already completed steps")
    parser.add_argument("--run-id",  help="Run ID from ggm-fe for linking")
    args = parser.parse_args()

    inputs = {"name": args.name}
    if args.image:
        inputs["imagePath"] = args.image

    steps = args.steps.split(",") if args.steps else None

    run_plugin(
        plugin_id=args.plugin,
        project_path=args.project,
        inputs=inputs,
        steps=steps,
        resume=args.resume,
        run_id=args.run_id,
    )
