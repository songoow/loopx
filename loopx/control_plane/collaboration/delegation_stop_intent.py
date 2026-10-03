"""Persisted stop intent, never inferred from signals or progress."""
from __future__ import annotations

import secrets
from pathlib import Path

from .inbox import _read, _write


DELEGATION_STOP_INTENT_SUFFIX = ".stop-intent.json"
DELEGATION_STOP_RECEIPT_SUFFIX = ".stop-receipt.json"


def stop_intent_path(record_path: Path) -> Path:
    """The intent beside the operation record, created before any fence write."""
    return record_path.with_suffix(DELEGATION_STOP_INTENT_SUFFIX)


def stop_receipt_path(record_path: Path) -> Path:
    """The receipt, derived from current facts on every read."""
    return record_path.with_suffix(DELEGATION_STOP_RECEIPT_SUFFIX)


def write_stop_intent(record_path: Path, requester: dict) -> dict:
    """Persist the explicit requester intent for this operation before fencing.

    The intent carries a stable stop_id and the requester identity. Repeated
    stops to the same operation return the same intent without changing it.
    """
    intent_path = stop_intent_path(record_path)
    if intent_path.exists():
        return _read(intent_path)
    intent = {
        "schema_version": "loopx_delegation_stop_intent_v0",
        "stop_id": secrets.token_urlsafe(16),
        "requester": {
            "goal_id": requester["goal_id"],
            "agent_id": requester["agent_id"],
        },
    }
    _write(intent_path, intent)
    return intent


def read_stop_intent(record_path: Path) -> dict | None:
    """Read the persisted intent, or None when no stop was requested."""
    intent_path = stop_intent_path(record_path)
    try:
        return _read(intent_path) if intent_path.exists() else None
    except (OSError, ValueError, KeyError):
        return None
