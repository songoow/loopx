"""Explicit inference outside the control-plane invocation; bounded parallelism."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
from pathlib import Path
import re
import time
from typing import Any, Callable

from loopx.control_plane.ranking_context import snapshot_id
from .config import Config, read_json
from .protocol import QUESTION_VERSION, PreferenceUnavailable, build_request, decode_order, request_bytes
from .store import RunStore
from .transport import TransportFailure, send

SECRET = re.compile(r"apikey_[A-Za-z0-9_]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|sk-[A-Za-z0-9_-]{24,}")


def read_basis(path: Path, workspace: Path) -> tuple[dict[str, Any], Callable[[], bool]]:
    """Read operator-supplied criterion plus exact local evidence; no remote dereference."""
    manifest, manifest_hash = read_json(path, 32768)
    allowed = {"goal_id", "objective", "acceptance", "non_goals", "horizon", "evidence", "already_known"}
    if not isinstance(manifest, dict) or set(manifest) - allowed:
        raise ValueError("unknown basis fields")
    if not isinstance(manifest.get("objective"), str) or not manifest["objective"].strip():
        raise ValueError("an explicit operator objective is required")
    if (not isinstance(manifest.get("acceptance"), list) or not manifest["acceptance"]
            or any(not isinstance(x, str) or not x.strip() for x in manifest["acceptance"])):
        raise ValueError("explicit acceptance criteria are required")
    references = manifest.get("evidence", [])
    if not isinstance(references, list) or len(references) > 8:
        raise ValueError("at most eight local evidence references")
    observations, checks = [], []
    total = 0
    for item in references:
        if not isinstance(item, dict) or set(item) - {"ref", "description"} or not isinstance(item.get("ref"), str):
            raise ValueError("evidence requires a relative ref, not a claimed observation")
        relative = Path(item["ref"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("evidence escapes the selected workspace")
        target = workspace / relative
        if target.is_symlink() or not target.resolve().is_relative_to(workspace.resolve()) or not target.is_file():
            raise ValueError("evidence must be a regular workspace file")
        with target.open("rb") as stream:
            raw = stream.read(32769)
        total += len(raw)
        if total > 32768:
            raise ValueError("evidence byte budget exceeded")
        digest = hashlib.sha256(raw).hexdigest()
        observations.append({"ref": item["ref"], "sha256": digest,
                             "text": raw.decode("utf-8"), "origin": "host_file_read",
                             "description": item.get("description", "")})
        checks.append((target, digest))
    basis = {**manifest, "evidence": observations,
             "basis_origin": "explicit_operator_study_basis_not_completion_authority"}
    def current():
        try:
            if read_json(path, 32768)[1] != manifest_hash:
                return False
            for target, digest in checks:
                if target.is_symlink() or not target.resolve().is_relative_to(workspace.resolve()):
                    return False
                with target.open("rb") as stream:
                    raw = stream.read(32769)
                if len(raw) > 32768 or hashlib.sha256(raw).hexdigest() != digest:
                    return False
            return True
        except (OSError, ValueError):
            return False
    return basis, current


def assess_one(snapshot: dict[str, Any], basis: dict[str, Any], config: Config, store: RunStore,
               guard: Callable[[], bool], transport: Callable = send,
               credential: Callable[[], str | None] | None = None) -> dict[str, Any]:
    clock_started = clock_previous = time.perf_counter_ns()
    timings = {}
    def mark(name):
        nonlocal clock_previous
        now = time.perf_counter_ns()
        timings[name] = now - clock_previous
        clock_previous = now
    from .advisory import Direction
    builder, decoder, version = build_request, decode_order, QUESTION_VERSION
    output_key = "order"
    output_value = list
    if snapshot.get("scenario") in set(Direction):
        from .advisory import build_request as advisory_request, decode_assessment, QUESTION_VERSION as advisory_version
        builder, decoder, version = advisory_request, decode_assessment, advisory_version
        output_key, output_value = "assessment", dict
    identity = snapshot_id(snapshot)
    result = {"snapshot_id": identity, "scenario": snapshot.get("scenario"), "status": "not_evaluated",
              "dispatch": "not_sent", "order": None, "usage": None, "cost_usd": None,
              "assessment_timing_ns": timings}
    if config.mode == "off" or snapshot.get("scenario") not in config.scenarios:
        return {**result, "reason": "disabled"}
    if not config.allow_egress:
        return {**result, "reason": "egress_denied"}
    if not guard():
        return {**result, "reason": "revoked_or_stale"}
    mark("eligibility_guard")
    try:
        request, pairs = builder(snapshot, basis, config.model, config.max_candidates)
    except (ValueError, KeyError, TypeError) as exc:
        return {**result, "reason": str(exc) if isinstance(exc, ValueError) else "invalid_snapshot"}
    raw = request_bytes(request)
    if len(raw) > config.max_request_bytes:
        return {**result, "reason": "request_too_large"}
    if SECRET.search(raw.decode("utf-8")):
        return {**result, "reason": "credential_like_material_rejected"}
    key = credential() if credential is not None else os.environ.get("TYPESAFE_API_KEY")
    if not key:
        return {**result, "reason": "missing_key"}
    request_id = hashlib.sha256(request_bytes({"snapshot": identity, "request": request,
                                               "question_version": version,
                                               "config_generation": config.generation,
                                               "source_basis": basis.get("source_basis")})).hexdigest()
    mark("request_preparation")
    try:
        previous = store.reserve(request_id, config.max_requests_per_run)
    except (OSError, ValueError):
        return {**result, "reason": "attempt_store_unavailable"}
    mark("reservation")
    if previous is not None:
        if previous.get("request_id") == request_id and previous.get("response") is not None:
            try:
                order = decoder(previous["response"], snapshot, pairs, config.model,
                                     config.minimum_preference_probability)
            except PreferenceUnavailable:
                # Abstentions still require a fresh guard and replay measurements.
                order = None
            except (ValueError, KeyError, TypeError):
                return {**result, "reason": "invalid_cached_result", "dispatch": previous.get("dispatch")}
            if guard():
                mark("replay_decode_and_guard")
                return {**previous, output_key: output_value(order) if order is not None else None, "replayed": True,
                        "assessment_timing_ns": timings,
                        "cached_provider_measurements": True,
                        "assessment_total_ns": time.perf_counter_ns() - clock_started}
            return {**result, "status": "stale", "reason": "revoked_or_stale_on_replay",
                    "dispatch": previous.get("dispatch"), "replayed": True}
        return {**result, "reason": previous.get("status", "prior_attempt_unresolved"),
                "dispatch": previous.get("dispatch", "may_have_been_sent"), "replayed": True}
    started = time.monotonic()
    result.update(request_id=request_id, question_version=version,
                  requested_model=config.model, config_generation=config.generation,
                  input_bytes=len(raw), execution_kind="live_provider" if transport is send else "fixture_injected")
    try:
        if not guard():
            result["reason"] = "revoked_before_send"
        else:
            mark("pre_dispatch_guard")
            try:
                envelope = transport(request, config, key)
            finally:
                mark("transport_inclusive")
            for timing_key in ("transport_timing_ns", "worker_timing_ns"):
                timing = envelope.get(timing_key)
                if isinstance(timing, dict) and all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in timing.values()):
                    result[timing_key] = timing
            response = envelope["response"]
            result["dispatch"] = "response_received"
            unavailable = None
            try:
                order = decoder(response, snapshot, pairs, config.model,
                                     config.minimum_preference_probability)
            except PreferenceUnavailable as exc:
                order = None
                unavailable = str(exc)
            result["actual_model"] = config.model
            # Never persist optional/free-text provider fields or reflected inputs.
            saved_response = {"model": config.model, "answers": {
                name: {key: answer[key] for key in ("type", "choice", "probabilities", "confidence") if key in answer}
                for name, answer in response["answers"].items()
            }}
            usage = response.get("usage")
            if isinstance(usage, dict):
                result["usage"] = {k: v for k, v in usage.items() if k in {"input_tokens", "output_tokens"}
                                   and isinstance(v, int) and not isinstance(v, bool) and v >= 0}
            result.update(response=saved_response)
            mark("response_validation")
            if not guard():
                result.update(status="stale", reason="revoked_or_stale_after_response")
            elif unavailable:
                result.update(status="abstained" if unavailable == "insufficient_evidence_or_uncertain" else "inconsistent",
                              reason=unavailable)
            else:
                result.update(status="completed", reason=None)
                result[output_key] = output_value(order)
                if output_key == "assessment" and not order["coverage"]["decided"]:
                    result.update(status="abstained", reason="insufficient_evidence_or_uncertain")
    except TransportFailure as exc:
        result.update(status="failed", reason=exc.code, dispatch=exc.dispatch)
    except (ValueError, TypeError, KeyError, OSError):
        result.update(status="failed", reason="invalid_response_or_local_io",
                      dispatch="may_have_been_sent" if result["dispatch"] == "not_sent" else result["dispatch"])
    mark("completion_or_failure")
    result["elapsed_ms"] = round((time.monotonic() - started) * 1000)
    try:
        store.finish(request_id, result)
    except (OSError, ValueError):
        # The existing reservation still prevents a silent repeat. Do not consume
        # an unrecorded answer or turn this optional write failure into work failure.
        result.update(status="failed", order=None, reason="attempt_result_unavailable")
        result.pop("assessment", None)
    mark("result_write")
    result["assessment_total_ns"] = time.perf_counter_ns() - clock_started
    return result


def assess_all(snapshots: dict[str, dict], basis: dict, config: Config, store: RunStore,
               guard: Callable[[], bool], transport: Callable = send,
               credential: Callable[[], str | None] | None = None) -> list[dict]:
    if config.mode == "off":
        return []
    # Map preserves the capture order; the shared ledger serializes reservations.
    with ThreadPoolExecutor(max_workers=config.max_parallel, thread_name_prefix="jev-assessment") as pool:
        return list(pool.map(lambda snapshot: assess_one(snapshot, basis, config, store, guard, transport, credential),
                             snapshots.values()))
