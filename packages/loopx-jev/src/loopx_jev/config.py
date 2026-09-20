"""Strict, explicit local configuration; never appended to old LoopX profiles."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from .advisory import Direction


def strict_json(raw: str | bytes) -> Any:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    def bad_constant(_):
        raise ValueError("non-finite JSON value")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=bad_constant)


def read_json(path: Path, limit: int = 1024 * 1024) -> tuple[Any, str]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("expected a regular local file")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("input exceeds byte limit")
    return strict_json(raw), hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class Config:
    mode: str = "off"
    scenarios: tuple[str, ...] = ("todo_order", "explore_order")
    model: str = ""
    allow_egress: bool = False
    max_candidates: int = 6
    deadline_ms: int = 5000
    max_requests_per_run: int = 20
    max_parallel: int = 2
    max_request_bytes: int = 65536
    max_response_bytes: int = 65536
    minimum_preference_probability: float = 0.6
    generation: str = "off"


def load_config(path: Path | None) -> Config:
    if path is None:
        return Config()
    obj, generation = read_json(path, 16384)
    allowed = {"schema_version", "mode", "scenarios", "model", "allow_egress", "limits",
               "minimum_preference_probability"}
    if not isinstance(obj, dict) or set(obj) - allowed:
        raise ValueError("unknown Jev configuration fields")
    if obj.get("schema_version") != "loopx_jev_branch_config_v0":
        raise ValueError("unsupported Jev configuration")
    mode = obj.get("mode", "off")
    if mode not in {"off", "shadow", "assist"}:
        raise ValueError("mode must be off, shadow or assist")
    scenarios = obj.get("scenarios", ["todo_order", "explore_order"])
    if (not isinstance(scenarios, list) or not scenarios or len(set(scenarios)) != len(scenarios)
            or any(x not in {"todo_order", "explore_order", *Direction} for x in scenarios)):
        raise ValueError("unsupported selection scenario")
    model = obj.get("model", "")
    if not isinstance(model, str) or len(model) > 120:
        raise ValueError("invalid requested model")
    if mode != "off" and (not model.strip() or "latest" in model.lower()):
        raise ValueError("enabled mode requires an explicit pinned model")
    egress = obj.get("allow_egress", False)
    if not isinstance(egress, bool):
        raise ValueError("allow_egress must be boolean")
    limits = obj.get("limits", {})
    bounds = {"max_candidates": (2, 6), "deadline_ms": (100, 30000),
              "max_requests_per_run": (1, 100), "max_parallel": (1, 4),
              "max_request_bytes": (1024, 131072), "max_response_bytes": (1024, 131072)}
    if not isinstance(limits, dict) or set(limits) - set(bounds):
        raise ValueError("unknown request limits")
    for name, value in limits.items():
        low, high = bounds[name]
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            raise ValueError(f"invalid {name}")
    minimum = obj.get("minimum_preference_probability", 0.6)
    if isinstance(minimum, bool) or not isinstance(minimum, (int, float)) or not 0.5 <= minimum <= 1:
        raise ValueError("invalid preference probability threshold")
    return Config(mode=mode, scenarios=tuple(scenarios), model=model, allow_egress=egress,
                  generation=generation, minimum_preference_probability=minimum, **limits)
