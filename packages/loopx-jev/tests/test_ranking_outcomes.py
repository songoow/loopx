"""Finite judgments through both real owners; fixtures prove boundaries, not quality."""

import pytest

from loopx.control_plane.ranking_context import ranking_context
from loopx_jev.config import Config
from loopx_jev.demo import select_todo, plan_explore
from loopx_jev.runner import assess_one
from loopx_jev.store import initialize_run, RunStore
from loopx_jev.transport import TransportFailure


def explore_selected():
    return plan_explore()["selected_worker_branches"][0]["branch_id"]


@pytest.mark.parametrize("owner", [select_todo, explore_selected], ids=["d7", "d8"])
@pytest.mark.parametrize(
    "judgment",
    [
        "prefer_other",
        "prefer_baseline",
        "tie",
        "unknown",
        "uncertain",
        "timeout",
        "revoked",
    ],
)
def test_judgment_pipeline_preserves_owner_fallback(tmp_path, owner, judgment):
    with ranking_context() as capture:
        baseline = owner()
    identity, snapshot = next(iter(capture.snapshots.items()))
    other = next(x for x in snapshot["baseline_order"] if x != baseline)
    current = [True]
    calls = []

    def transport(request, config, key):
        calls.append(request)
        if judgment == "timeout":
            raise TransportFailure("deadline_exceeded", "may_have_been_sent")
        left = sorted(snapshot["baseline_order"])[0]
        wanted = other if judgment == "prefer_other" else baseline
        choice = "left" if wanted == left else "right"
        if judgment == "tie":
            choice = "tie"
        if judgment == "unknown":
            choice = "insufficient_evidence"
        probabilities = {
            k: float(k == choice)
            for k in ("left", "right", "tie", "insufficient_evidence")
        }
        if judgment == "uncertain":
            probabilities = {
                "left": 0.51,
                "right": 0.49,
                "tie": 0.0,
                "insufficient_evidence": 0.0,
            }
            choice = "left"
        if judgment == "revoked":
            current[0] = False
        return {
            "response": {
                "model": config.model,
                "answers": {
                    name: {
                        "type": "choice",
                        "choice": choice,
                        "probabilities": probabilities,
                    }
                    for name in request["questions"]
                },
            }
        }

    initialize_run(tmp_path / "run", 1)
    record = assess_one(
        snapshot,
        {
            "objective": "Produce independent compatibility evidence",
            "acceptance": ["independent check passes"],
        },
        Config(mode="assist", model="fixture-v1", allow_egress=True),
        RunStore(tmp_path / "run"),
        lambda: current[0],
        transport,
        lambda: "fixture",
    )
    preferences = {identity: record["order"]} if record["status"] == "completed" else {}
    with ranking_context(preferences=preferences, guard=lambda: current[0]) as consumed:
        selected = owner()
    assert len(calls) == 1
    assert selected == (other if judgment == "prefer_other" else baseline)
    expected_status = {
        "unknown": "abstained",
        "uncertain": "abstained",
        "timeout": "failed",
        "revoked": "stale",
    }.get(judgment, "completed")
    assert record["status"] == expected_status
    assert any(e["status"] == "preference_consumed" for e in consumed.events) == (
        expected_status == "completed"
    )


@pytest.mark.parametrize("owner", [select_todo, explore_selected], ids=["d7", "d8"])
def test_cached_abstention_has_fresh_timing_and_obeys_revocation(tmp_path, owner):
    with ranking_context() as capture:
        owner()
    snapshot = next(iter(capture.snapshots.values()))
    initialize_run(tmp_path / "run", 1)
    store = RunStore(tmp_path / "run")
    config = Config(mode="assist", model="fixture-v1", allow_egress=True)
    basis = {
        "objective": "Investigate unknown behavior",
        "acceptance": ["independent evidence"],
    }
    calls = []

    def transport(request, config, key):
        calls.append(1)
        return {
            "response": {
                "model": config.model,
                "answers": {
                    name: {
                        "type": "choice",
                        "choice": "insufficient_evidence",
                        "probabilities": {
                            "left": 0.0,
                            "right": 0.0,
                            "tie": 0.0,
                            "insufficient_evidence": 1.0,
                        },
                    }
                    for name in request["questions"]
                },
            }
        }

    first = assess_one(
        snapshot, basis, config, store, lambda: True, transport, lambda: "fixture"
    )
    replay = assess_one(
        snapshot, basis, config, store, lambda: True, transport, lambda: "fixture"
    )
    assert first["status"] == replay["status"] == "abstained"
    assert replay["replayed"] and replay["cached_provider_measurements"]
    assert "transport_inclusive" not in replay["assessment_timing_ns"]
    assert replay["assessment_total_ns"] >= 0
    guards = iter([True, False])
    revoked = assess_one(
        snapshot,
        basis,
        config,
        store,
        lambda: next(guards),
        transport,
        lambda: "fixture",
    )
    assert revoked["status"] == "stale" and revoked["order"] is None
    assert len(calls) == 1


@pytest.mark.parametrize("width", [2, 3, 4, 5, 6])
def test_ranking_is_invariant_to_every_baseline_permutation(width):
    """A supported strict order must survive presentation changes at every legal width."""
    from itertools import permutations
    from loopx_jev.protocol import build_request, decode_order

    ids = list("abcdef"[:width])
    expected = tuple(reversed(ids))
    for baseline in permutations(ids):
        snapshot = {
            "baseline_order": list(baseline),
            "cohorts": [ids],
            "cards": [{"id": x, "todo": {"text": "Candidate " + x}} for x in baseline],
        }
        request, pairs = build_request(
            snapshot, {"objective": "Compare work", "acceptance": ["Evidence"]}, "v1"
        )
        assert len(pairs) == width * (width - 1) // 2
        # Lexically greater IDs win in this injected total order, irrespective of slots.
        answers = {
            name: {
                "type": "choice",
                "choice": "right",
                "probabilities": {
                    "left": 0.0,
                    "right": 1.0,
                    "tie": 0.0,
                    "insufficient_evidence": 0.0,
                },
            }
            for name in pairs
        }
        assert (
            decode_order({"model": "v1", "answers": answers}, snapshot, pairs, "v1")
            == expected
        )


def test_interleaved_policy_cohorts_keep_slots_and_never_generate_cross_group_questions():
    from loopx_jev.protocol import build_request, decode_order

    snapshot = {
        "baseline_order": ["a", "b", "c", "d"],
        "cohorts": [["a", "c"], ["b", "d"]],
        "cards": [{"id": x, "todo": {"text": x}} for x in "abcd"],
    }
    request, pairs = build_request(
        snapshot, {"objective": "Compare work", "acceptance": ["Evidence"]}, "v1"
    )
    assert set(pairs.values()) == {("a", "c"), ("b", "d")}
    answers = {
        name: {
            "type": "choice",
            "choice": "right",
            "probabilities": {
                "left": 0.0,
                "right": 1.0,
                "tie": 0.0,
                "insufficient_evidence": 0.0,
            },
        }
        for name in pairs
    }
    assert decode_order({"model": "v1", "answers": answers}, snapshot, pairs, "v1") == (
        "c",
        "d",
        "a",
        "b",
    )


def test_no_comparable_pair_does_not_read_key_or_spend_request_budget(tmp_path):
    snapshot = {
        "scenario": "todo_order",
        "baseline_order": ["a", "b"],
        "cohorts": [["a"], ["b"]],
        "cards": [{"id": x, "todo": {"text": x}} for x in "ab"],
    }

    def forbidden(*args):
        pytest.fail("no legal comparison must not dispatch or read credentials")

    initialize_run(tmp_path / "run", 1)
    before = (tmp_path / "run/manifest.json").read_bytes()
    result = assess_one(
        snapshot,
        {"objective": "Compare", "acceptance": ["Evidence"]},
        Config(mode="assist", model="v1", allow_egress=True),
        RunStore(tmp_path / "run"),
        lambda: True,
        forbidden,
        forbidden,
    )
    assert result["reason"] == "no_comparable_pair" and result["dispatch"] == "not_sent"
    assert (tmp_path / "run/manifest.json").read_bytes() == before
    assert [p.name for p in (tmp_path / "run").iterdir()] == ["manifest.json"]
