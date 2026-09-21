"""Synthetic work through the actual TS selector/Explore planner, then real file validation.

The fixture provider checks integration only. --live uses actual Jev; neither
mode is a live Codex/Claude run or a canonical completion/settlement certificate.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from loopx.control_plane.ranking_context import ranking_context
from .config import Config
from .runner import assess_all
from .store import initialize_run, RunStore, atomic_json
from .transport import send


def todo_inputs():
    gates = [{"todo_id": "todo_gate", "status": "open", "task_class": "user_gate",
              "blocks_agent": "agent-a", "unblocks_todo_id": "todo_publish",
              "action_kind": "publish_report"}]
    todos = [{"todo_id": "todo_polish", "text": "Polish wording of existing diagnostic messages",
              "status": "open", "priority": "P1", "index": 1, "task_class": "advancement_task"},
             {"todo_id": "todo_fixture", "text": "Create independent legacy format fixture needed for compatibility verification",
              "status": "open", "priority": "P1", "index": 2, "task_class": "advancement_task"},
             {"todo_id": "todo_publish", "text": "Publish the new release", "status": "open",
              "priority": "P0", "index": 0, "task_class": "advancement_task"}]
    return gates, todos


def select_todo():
    from loopx.control_plane.todos.decision_scope import select_scoped_gate_fallback
    gates, todos = todo_inputs()
    result = select_scoped_gate_fallback(gates, todos, agent_id="agent-a", allow_unrelated_gate=True,
                                        monitor_debt_backoff_active=False)
    return todos[result["selected_index"]]["todo_id"]


def explore_inputs():
    return dict(goal_id="goal-demo", agent_id="agent-a", todos=[
        {"todo_id": "todo_repeat", "text": "Repeat the already-passed plain ASCII test",
         "status": "open", "priority": "P1", "index": 1, "task_class": "advancement_task",
         "required_write_scopes": ["artifacts/normal/**"]},
        {"todo_id": "todo_probe", "text": "Probe decomposed Unicode combining marks to distinguish the untested normalization hypothesis",
         "status": "open", "priority": "P1", "index": 2, "task_class": "advancement_task",
         "required_write_scopes": ["artifacts/unicode/**"]}],
        orchestration={"spawn_allowed": True, "max_children": 1,
                       "explore_harness": {"enabled": True, "max_worker_lanes": 1}},
        worker_width=1, max_todos_per_branch=1, harness_profile="generic")


def plan_explore():
    from loopx.capabilities.explore.worker_branch_plan import build_explore_worker_branch_plan
    return build_explore_worker_branch_plan(**explore_inputs())


def fixture_response(request, config, key):
    # Deliberately injected oracle; not an imitation of a measured Jev result.
    cards = request["state"]["cards"]
    favored = next(c["id"] for c in cards if "fixture" in c["id"] or "unicode" in c["id"])
    answers = {}
    for name, question in request["questions"].items():
        left = question["instructions"].split("(id ", 1)[1].split(")", 1)[0]
        right = question["instructions"].split("(id ", 2)[2].split(")", 1)[0]
        choice = "left" if favored == left else "right" if favored == right else "tie"
        answers[name] = {"type": "choice", "choice": choice, "confidence": 1.0,
                         "probabilities": {v: float(v == choice) for v in ("left", "right", "tie", "insufficient_evidence")}}
    return {"dispatch": "response_received", "response": {"model": config.model, "answers": answers}}


def _execute_fixture(root: Path, scenario: str, selected: str) -> dict:
    root.mkdir()
    # Actual subprocess writes an artifact. An independent reader checks content;
    # this is not evidence that a real coding model produced the artifact.
    host = '''import json, pathlib, sys, unicodedata
scenario, selected = sys.argv[1:]
if scenario == 'todo_order':
    value = {'legacy_version': 0, 'payload': ['é']} if selected == 'todo_fixture' else {'diagnostic_wording': 'improved'}
else:
    value = {'probe': 'combining' if 'unicode' in selected else 'ascii',
             'equal_after_nfc': unicodedata.normalize('NFC', 'e\\u0301') == 'é'}
pathlib.Path('artifact.json').write_text(json.dumps(value))
'''
    completed = subprocess.run([sys.executable, "-c", host, scenario, selected], cwd=root,
                               capture_output=True, timeout=10, check=True)
    value = json.loads((root / "artifact.json").read_text())
    meaningful = value.get("legacy_version") == 0 if scenario == "todo_order" else (
        value.get("probe") == "combining" and value.get("equal_after_nfc") is True)
    return {"host_exit_code": completed.returncode, "artifact_exists": True,
            "fixture_target_evidence": meaningful,
            "execution_kind": "synthetic_subprocess_host", "canonical_completion": "not_exercised"}


def run_demo(output: Path, *, live: bool = False, model: str = "jev-1.13.0",
             ranking_policy: str = "pairwise") -> int:
    if output.exists():
        raise ValueError("use a new isolated output directory")
    output.mkdir(parents=True, mode=0o700)
    initialize_run(output / "attempts", max_requests=2)
    store = RunStore(output / "attempts")
    config = Config(mode="assist", model=model, allow_egress=True, max_requests_per_run=2,
                    deadline_ms=5000, generation=f"isolated-demo-v1-{ranking_policy}",
                    ranking_policy=ranking_policy)
    basis = {"goal_id": "goal-demo", "objective": "Establish independently checkable backward compatibility and Unicode evidence",
             "acceptance": ["A real legacy fixture exists", "The normalization boundary is independently probed"],
             "horizon": "one bounded next work item", "already_known": "Plain ASCII already passes"}
    records = []
    assessments = []
    for scenario, operation in (("todo_order", select_todo), ("explore_order", plan_explore)):
        with ranking_context() as initial:
            operation()
        results = assess_all(initial.snapshots, basis, config, store, lambda: True,
                             send if live else fixture_response,
                             None if live else lambda: "fixture-only-not-a-credential")
        assessments.extend(results)
        preferences = {r["snapshot_id"]: r["order"] for r in results if r["status"] == "completed"}
        for mode in ("off", "shadow", "assist"):
            with ranking_context(preferences=preferences if mode == "assist" else None) as state:
                value = operation()
            selected = value if scenario == "todo_order" else value["selected_worker_branches"][0]["branch_id"]
            execution = _execute_fixture(output / f"{scenario}-{mode}", scenario, selected)
            records.append({"scenario": scenario, "mode": mode, "selected": selected,
                            "events": state.events, "execution": execution})
        atomic_json(output / f"{scenario}-assessment.json", results)
    report = {"provider_kind": "live_jev" if live else "fixture_injected", "ranking_policy": ranking_policy,
              "coding_host": "synthetic_subprocess_not_codex_or_claude", "records": records,
              "assessments": [{k: r.get(k) for k in ("scenario", "status", "dispatch", "reason", "actual_model", "usage")} for r in assessments],
              "boundary": "Demonstrates selected-work plumbing, not general model benefit or canonical settlement."}
    atomic_json(output / "comparison.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 3 if live and any(r["status"] not in {"completed", "abstained", "inconsistent"} for r in assessments) else 0
