"""Two-stage capture/execute wrapper: inference never runs inside a LoopX reducer."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Callable

from .config import load_config, read_json


def _original(argv: list[str]) -> int:
    from loopx.entrypoint import main
    return main(argv)


def _arguments(argv: list[str]) -> list[str]:
    result = list(argv)
    if result[:1] == ["--"]:
        result.pop(0)
    if result[:1] == ["loopx"]:
        result.pop(0)
    index = 0
    while index < len(result) and result[index].startswith("--"):
        option, separator, value = result[index].partition("=")
        if option not in {"--format", "--registry", "--runtime-root"}:
            raise ValueError("unsupported global option in pilot wrapper")
        if separator:
            if not value:
                raise ValueError("missing global option value")
            index += 1
        else:
            if index + 1 >= len(result) or result[index + 1].startswith("--"):
                raise ValueError("missing global option value")
            index += 2
    allowed = result[index:index + 2] in (["quota", "should-run"], ["explore", "worker-branch-plan"])
    if not allowed:
        raise ValueError("pilot capture/run supports quota should-run or explore worker-branch-plan only")
    return result


def _implementation() -> dict[str, str]:
    import loopx
    root = Path(loopx.__file__).resolve().parent
    paths = ["control_plane/ranking_context.py", "control_plane/todos/decision_scope.py",
             "control_plane/todos/decision_scope.ts", "capabilities/explore/worker_branch_plan.py"]
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in paths}


def _source_basis(argv: list[str]) -> dict:
    """Read the actual selected registry/provider version; never promote or fall back.

    Pilot capture requires explicit local paths. This is a version vector with
    before/after checks, not a claim of a cross-store atomic snapshot.
    """
    from loopx.control_plane.coordination.local_authority import read_canonical_todos_if_promoted
    values = {}
    for index, argument in enumerate(argv):
        option, separator, value = argument.partition("=")
        if option in {"--registry", "--runtime-root", "--goal-id"}:
            values[option] = value if separator else argv[index + 1]
    if set(values) != {"--registry", "--runtime-root", "--goal-id"}:
        raise ValueError("capture requires explicit registry, runtime-root and goal-id")
    registry, registry_hash = read_json(Path(values["--registry"]), 4 * 1024 * 1024)
    goal = next(row for row in registry["goals"] if row["id"] == values["--goal-id"])
    current = read_canonical_todos_if_promoted(runtime_root=Path(values["--runtime-root"]),
                                              goal_id=values["--goal-id"], include_leases=True)
    basis = {"registry_sha256": registry_hash, "goal_id": values["--goal-id"]}
    if current is not None:
        basis.update(source=current["source_authority"], provider_revision=current["provider_revision"])
    else:
        state = Path(goal["state_file"])
        if not state.is_absolute():
            state = Path(goal["repo"]) / state
        if state.is_symlink() or not state.is_file():
            raise ValueError("legacy state unavailable")
        with state.open("rb") as stream:
            raw = stream.read(4 * 1024 * 1024 + 1)
        if len(raw) > 4 * 1024 * 1024:
            raise ValueError("legacy source exceeds capture limit")
        basis.update(source="legacy_markdown", state_sha256=hashlib.sha256(raw).hexdigest())
    return basis


def capture(argv: list[str], output: Path, invoke: Callable = _original) -> int:
    from loopx.control_plane.ranking_context import ranking_context
    from .store import atomic_json
    argv = _arguments(argv)
    if output.exists():
        raise ValueError("capture path already exists; use a new explicit path")
    if not output.parent.is_dir():
        raise ValueError("capture parent directory must exist")
    before = _source_basis(argv)
    with ranking_context() as context:
        code = invoke(argv)
    after = _source_basis(argv)
    atomic_json(output, {"format": "jev_capture_v0", "created_at": time.time(),
                         "cwd": str(Path.cwd().resolve()), "argv": argv,
                         "implementation": _implementation(), "exit_code": code,
                         "source_basis": after, "source_stable": before == after,
                         "snapshots": context.snapshots, "events": context.events})
    return code


def execute(argv: list[str], *, config_path: Path | None, capture_path: Path | None,
            basis_path: Path | None, run_dir: Path | None, report_path: Path | None,
            invoke: Callable = _original, transport=None, credential=None) -> int:
    config = load_config(config_path)
    argv = _arguments(argv)
    # Off touches no capture, basis, run directory, credential, transport or report.
    if config.mode == "off":
        return invoke(argv)
    from loopx.control_plane.ranking_context import ranking_context, snapshot_id
    from .runner import assess_all, read_basis
    from .store import RunStore, atomic_json
    from .transport import send

    if any(value is None for value in (capture_path, basis_path, run_dir, report_path)):
        raise ValueError("enabled mode requires capture, basis, run-dir and report")
    captured, _ = read_json(capture_path, 4 * 1024 * 1024)
    if (captured.get("format") != "jev_capture_v0" or captured.get("argv") != argv
            or captured.get("cwd") != str(Path.cwd().resolve())
            or captured.get("implementation") != _implementation()
            or captured.get("exit_code") != 0 or captured.get("source_stable") is not True):
        raise ValueError("capture identity/source/command mismatch; recapture the actual entrypoint")
    snapshots = captured.get("snapshots")
    if not isinstance(snapshots, dict) or len(snapshots) > 32:
        raise ValueError("invalid capture")
    for key, value in snapshots.items():
        if snapshot_id(value) != key:
            raise ValueError("capture digest mismatch")
    basis, basis_current = read_basis(basis_path, Path.cwd())
    goal = basis.get("goal_id")
    if not isinstance(goal, str) or not goal:
        raise ValueError("basis requires a goal_id matching the command")
    goal_arg = None
    for i, arg in enumerate(argv):
        if arg == "--goal-id" and i + 1 < len(argv):
            goal_arg = argv[i + 1]
        elif arg.startswith("--goal-id="):
            goal_arg = arg.split("=", 1)[1]
    if goal_arg != goal:
        raise ValueError("basis Goal does not match command scope")
    basis["source_basis"] = captured["source_basis"]
    store = RunStore(run_dir)
    def current():
        try:
            now = load_config(config_path)
            return (now.mode == config.mode and now.generation == config.generation and basis_current()
                    and _source_basis(argv) == captured["source_basis"])
        except (OSError, ValueError, RuntimeError, KeyError, StopIteration):
            return False
    # Shadow invokes the real workflow first. It never exposes advice to it and
    # does not delay selection awaiting inference. Optional evaluation follows.
    if config.mode == "shadow":
        code = invoke(argv)
        results = assess_all(snapshots, basis, config, store, current, transport or send, credential)
        events = []
    else:
        results = assess_all(snapshots, basis, config, store, current, transport or send, credential)
        preferences = {r["snapshot_id"]: r["order"] for r in results
                       if r["status"] == "completed" and r["order"] is not None}
        # The current original selector recomputes the snapshot. Different facts
        # do not match; its current baseline is used instead of an old cached choice.
        with ranking_context(preferences=preferences, guard=current) as context:
            code = invoke(argv)
        events = context.events
    atomic_json(report_path, {"format": "jev_branch_report_v0", "mode": config.mode,
                              "implementation": _implementation(), "upstream_exit_code": code,
                              "assessments": results, "consumption": events,
                              "boundary": "local selector/planner observations; not dispatch or completion receipts"})
    return code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init-run", help="explicitly create a finite private attempt budget")
    init.add_argument("path", type=Path)
    init.add_argument("--max-requests", type=int, default=20)
    cap = commands.add_parser("capture", help="run an existing supported LoopX command and capture candidate facts")
    cap.add_argument("--output", type=Path, required=True)
    cap.add_argument("args", nargs=argparse.REMAINDER)
    run = commands.add_parser("run", help="precompute optional advice, then run the same original command")
    run.add_argument("--config", type=Path)
    run.add_argument("--capture", type=Path)
    run.add_argument("--basis", type=Path)
    run.add_argument("--run-dir", type=Path)
    run.add_argument("--report", type=Path)
    run.add_argument("args", nargs=argparse.REMAINDER)
    demo = commands.add_parser("demo", help="isolated actual-selector/planner examples; fixture provider by default")
    demo.add_argument("--output-dir", type=Path, required=True)
    demo.add_argument("--live", action="store_true")
    demo.add_argument("--model", default="jev-1.13.0")
    parsed = parser.parse_args(argv)
    try:
        if parsed.command == "init-run":
            from .store import initialize_run
            initialize_run(parsed.path, parsed.max_requests)
            print(json.dumps({"ok": True, "max_requests": parsed.max_requests}))
            return 0
        if parsed.command == "capture":
            return capture(parsed.args, parsed.output)
        if parsed.command == "demo":
            from .demo import run_demo
            return run_demo(parsed.output_dir, live=parsed.live, model=parsed.model)
        return execute(parsed.args, config_path=parsed.config, capture_path=parsed.capture,
                       basis_path=parsed.basis, run_dir=parsed.run_dir, report_path=parsed.report)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, StopIteration):
        # Private paths, input excerpts and credentials do not enter error output.
        print("loopx-jev: invalid configuration, unavailable input, or failed local validation", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
