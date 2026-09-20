"""Explicit host-owned capture/replay of bounded selection preferences.

There is no provider, network, configuration lookup or new authority here.
Absent an explicit context, existing callers keep their original behavior.
Only already-computed preferences may be consumed; a status poll never infers.
"""
from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
import hashlib
import json
from typing import Any


def snapshot_id(snapshot: Mapping[str, Any]) -> str:
    raw = json.dumps(snapshot, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def validate_preference(snapshot: Mapping[str, Any], order: Sequence[str]) -> tuple[str, ...]:
    baseline = snapshot["baseline_order"]
    cohorts = snapshot["cohorts"]
    if (not isinstance(order, (list, tuple)) or not isinstance(baseline, list)
            or any(not isinstance(x, str) or not x for x in [*baseline, *order])
            or len(set(baseline)) != len(baseline) or len(order) != len(baseline)
            or len(set(order)) != len(order) or set(order) != set(baseline)):
        raise ValueError("preference must be an exact candidate permutation")
    if not isinstance(cohorts, list) or any(not isinstance(g, list) or not g for g in cohorts):
        raise ValueError("invalid policy cohorts")
    membership: dict[str, int] = {}
    for i, group in enumerate(cohorts):
        for candidate in group:
            if not isinstance(candidate, str) or candidate in membership:
                raise ValueError("duplicate or invalid cohort member")
            membership[candidate] = i
    if set(membership) != set(baseline):
        raise ValueError("cohorts must cover every candidate")
    if any(membership[a] != membership[b] for a, b in zip(baseline, order, strict=True)):
        raise ValueError("preference crosses a policy cohort")
    return tuple(order)


@dataclass
class RankingContext:
    preferences: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    guard: Callable[[], bool] | None = None
    snapshots: dict[str, dict[str, Any]] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    max_snapshots: int = 32

    def emit(self, event: dict[str, Any]) -> None:
        if len(self.events) < 128:
            self.events.append(event)


_ACTIVE: ContextVar[RankingContext | None] = ContextVar("loopx_ranking_context", default=None)


def ranking_active() -> bool:
    return _ACTIVE.get() is not None


@contextmanager
def ranking_context(*, preferences: Mapping[str, Sequence[str]] | None = None,
                    guard: Callable[[], bool] | None = None) -> Iterator[RankingContext]:
    state = RankingContext(preferences={key: tuple(value) for key, value in (preferences or {}).items()},
                           guard=guard)
    token = _ACTIVE.set(state)
    try:
        yield state
    finally:
        _ACTIVE.reset(token)


def preference_for(snapshot: dict[str, Any]) -> tuple[str, ...] | None:
    """Capture current owner facts; look up a precomputed, exact-basis preference.

    ``guard`` is a trusted local revocation/freshness check, never an inference
    callback. Domain owners supply the policy cohorts, and recheck admission.
    """
    state = _ACTIVE.get()
    if state is None:
        return None
    try:
        identity = snapshot_id(snapshot)
        validate_preference(snapshot, snapshot["baseline_order"])
        encoded = json.dumps(snapshot, ensure_ascii=False, allow_nan=False)
        if len(encoded.encode("utf-8")) > 1024 * 1024:
            raise ValueError("selection snapshot exceeds limit")
        if identity not in state.snapshots and len(state.snapshots) >= state.max_snapshots:
            raise ValueError("selection snapshot count exceeds limit")
        state.snapshots[identity] = json.loads(encoded)
        order = state.preferences.get(identity)
        if order is None:
            state.emit({"snapshot_id": identity, "status": "baseline"})
            return None
        if state.guard is not None and not state.guard():
            state.emit({"snapshot_id": identity, "status": "revoked_or_stale"})
            return None
        result = validate_preference(snapshot, order)
        state.emit({"snapshot_id": identity, "status": "preference_consumed"})
        return result
    except (ValueError, TypeError, KeyError, OSError):
        state.emit({"status": "invalid_preference_or_snapshot"})
        return None


def record_selection(scenario: str, selected: Sequence[str]) -> None:
    state = _ACTIVE.get()
    if state is not None:
        state.emit({"scenario": scenario, "status": "owner_selection",
                             "selected": list(selected)})
