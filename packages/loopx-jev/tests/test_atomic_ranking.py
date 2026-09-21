"""Evidence-bound ranking through the real owners; fixtures do not prove model quality."""

import copy
import json

import pytest

from loopx.control_plane.ranking_context import ranking_context, snapshot_id
from loopx_jev.atomic_ranking import build_request, decode_order
from loopx_jev.config import Config, load_config
from loopx_jev.demo import select_todo, plan_explore
from loopx_jev.runner import assess_one, read_basis
from loopx_jev.store import initialize_run, RunStore


def explore():
    return plan_explore()["selected_worker_branches"][0]["branch_id"]


def setup(tmp_path, owner=select_todo):
    with ranking_context() as ctx:
        baseline = owner()
    snap = next(iter(ctx.snapshots.values()))
    (tmp_path / "observed.txt").write_text(
        "Current independent checks show a missing prerequisite and unchanged repeated evidence."
    )
    manifest = {
        "goal_id": "g",
        "objective": "Obtain new independent compatibility evidence",
        "acceptance": ["independent check passes"],
        "evidence": [{"ref": "observed.txt"}],
        "ranking_evidence": [
            {
                "snapshot_id": snapshot_id(snap),
                "candidates": {x: ["observed.txt"] for x in snap["baseline_order"]},
            }
        ],
    }
    (tmp_path / "basis.json").write_text(json.dumps(manifest))
    basis, guard = read_basis(tmp_path / "basis.json", tmp_path)
    return snap, basis, guard, baseline


def reply(request, favored, *, evidence="sufficient", advance="yes"):
    answers = {}
    for name, question in request["questions"].items():
        labels = list(question["criteria"])
        if name.startswith("evidence_"):
            label = evidence
        elif name.startswith("advance_"):
            label = advance
        else:
            left = question["instructions"].split("(id ", 1)[1].split(")", 1)[0]
            right = question["instructions"].split("(id ", 2)[2].split(")", 1)[0]
            label = (
                "left" if left == favored else "right" if right == favored else "tie"
            )
        answers[name] = {
            "type": "choice",
            "choice": label,
            "probabilities": {x: float(x == label) for x in labels},
        }
    return {"model": request["model"], "answers": answers}


@pytest.mark.parametrize("owner", [select_todo, explore], ids=["d7", "d8"])
@pytest.mark.parametrize(
    "evidence,advance,expected",
    [
        ("sufficient", "yes", "completed"),
        ("insufficient", "yes", "abstained"),
        ("conflicting", "yes", "abstained"),
        ("sufficient", "unknown", "abstained"),
        ("sufficient", "no", "abstained"),
    ],
)
def test_real_owner_adoption_and_fallback(tmp_path, owner, evidence, advance, expected):
    snap, basis, guard, baseline = setup(tmp_path, owner)
    favored = next(x for x in snap["baseline_order"] if x != baseline)
    initialize_run(tmp_path / "run", 1)
    config = Config(
        mode="assist",
        model="fixture-v1",
        allow_egress=True,
        ranking_policy="evidence_atomic",
    )

    def transport(request, *args):
        return {"response": reply(request, favored, evidence=evidence, advance=advance)}

    record = assess_one(
        snap,
        basis,
        config,
        RunStore(tmp_path / "run"),
        guard,
        transport,
        lambda: "fixture",
    )
    assert record["status"] == expected
    preferences = (
        {record["snapshot_id"]: record["order"]}
        if record["status"] == "completed"
        else {}
    )
    with ranking_context(preferences=preferences, guard=guard):
        assert owner() == (favored if expected == "completed" else baseline)
    assert record["ranking_decision"]["signals"]


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_candidate",
        "missing_ref",
        "unread",
        "stale_snapshot",
        "forged_digest",
        "duplicate_manifest",
    ],
)
def test_incomplete_input_never_reads_key_or_dispatches(tmp_path, mutation):
    snap, basis, guard, baseline = setup(tmp_path)
    binding = basis["ranking_evidence"][0]
    if mutation == "missing_candidate":
        binding["candidates"].pop(baseline)
    if mutation == "missing_ref":
        binding["candidates"][baseline] = []
    if mutation == "unread":
        binding["candidates"][baseline] = ["not-read.txt"]
    if mutation == "stale_snapshot":
        binding["snapshot_id"] = "old"
    if mutation == "forged_digest":
        basis["evidence"][0]["sha256"] = "claimed"
    if mutation == "duplicate_manifest":
        basis["ranking_evidence"].append(copy.deepcopy(binding))
    initialize_run(tmp_path / "run", 1)

    def forbidden(*args):
        pytest.fail("invalid evidence must not access provider credentials or network")

    result = assess_one(
        snap,
        basis,
        Config(
            mode="assist",
            model="v1",
            allow_egress=True,
            ranking_policy="evidence_atomic",
        ),
        RunStore(tmp_path / "run"),
        guard,
        forbidden,
        forbidden,
    )
    assert result["status"] == "not_evaluated" and result["dispatch"] == "not_sent"


def test_evidence_change_revokes_response_and_cached_result(tmp_path):
    snap, basis, guard, baseline = setup(tmp_path)
    initialize_run(tmp_path / "run", 2)
    config = Config(
        mode="assist", model="v1", allow_egress=True, ranking_policy="evidence_atomic"
    )
    store = RunStore(tmp_path / "run")

    def transport(request, *args):
        return {"response": reply(request, baseline)}

    assert (
        assess_one(snap, basis, config, store, guard, transport, lambda: "fixture")[
            "status"
        ]
        == "completed"
    )
    checks = iter([True, False])
    replay = assess_one(
        snap, basis, config, store, lambda: next(checks), transport, lambda: "fixture"
    )
    assert replay["status"] == "stale" and replay["order"] is None
    (tmp_path / "observed.txt").write_text("new source facts")
    assert not guard()
    assert (
        assess_one(snap, basis, config, store, guard, transport, lambda: "fixture")[
            "reason"
        ]
        == "revoked_or_stale"
    )


def test_atomic_mode_is_explicit_and_pairwise_remains_default(tmp_path):
    assert Config().ranking_policy == "pairwise"
    p = tmp_path / "config.json"
    p.write_text(
        json.dumps(
            {
                "schema_version": "loopx_jev_branch_config_v0",
                "ranking_policy": "invented",
            }
        )
    )
    with pytest.raises(ValueError, match="ranking policy"):
        load_config(p)
    p.write_text(
        json.dumps(
            {
                "schema_version": "loopx_jev_branch_config_v0",
                "ranking_policy": "evidence_atomic",
            }
        )
    )
    assert load_config(p).ranking_policy == "evidence_atomic"


def test_atomic_rejects_multiworker_and_mixed_policy_groups(tmp_path):
    snap, basis, _, _ = setup(tmp_path, explore)
    snap["source"]["width"] = 2
    with pytest.raises(ValueError, match="single_worker"):
        build_request(snap, basis, "v1")
    snap["cohorts"] = [[x] for x in snap["baseline_order"]]
    with pytest.raises(ValueError, match="single_policy"):
        build_request(snap, basis, "v1")


def test_unknown_tail_does_not_veto_proven_head_but_unknown_evidence_does(tmp_path):
    snap, basis, _, _ = setup(tmp_path)
    snap["baseline_order"] = ["a", "b", "c"]
    snap["cohorts"] = [["a", "b", "c"]]
    snap["cards"] = [{"id": x, "todo": {"text": x}} for x in "abc"]
    basis["ranking_evidence"] = [
        {
            "snapshot_id": snapshot_id(snap),
            "candidates": {x: ["observed.txt"] for x in "abc"},
        }
    ]
    request, domains = build_request(snap, basis, "v1")
    response = reply(request, "b")
    tail = next(
        k
        for k, (kind, target) in domains.items()
        if kind == "pair" and set(target) == {"a", "c"}
    )
    response["answers"][tail] = {
        "type": "choice",
        "choice": "insufficient_evidence",
        "probabilities": {
            "left": 0.0,
            "right": 0.0,
            "tie": 0.0,
            "insufficient_evidence": 1.0,
        },
    }
    assert decode_order(response, snap, domains, "v1").order == ("b", "a", "c")
    name = next(k for k, v in domains.items() if v == ("evidence", "c"))
    response["answers"][name] = {
        "type": "choice",
        "choice": "insufficient",
        "probabilities": {"sufficient": 0.0, "insufficient": 1.0, "conflicting": 0.0},
    }
    assert decode_order(response, snap, domains, "v1").order is None
    response["answers"][tail]["probabilities"]["left"] = float("nan")
    with pytest.raises(ValueError):
        decode_order(response, snap, domains, "v1")


def test_off_does_not_require_atomic_inputs(tmp_path):
    snap, _, _, _ = setup(tmp_path)
    initialize_run(tmp_path / "run", 1)

    def forbidden(*args):
        pytest.fail("off must not read evidence or credentials")

    result = assess_one(
        snap,
        {},
        Config(ranking_policy="evidence_atomic"),
        RunStore(tmp_path / "run"),
        forbidden,
        forbidden,
        forbidden,
    )
    assert result["reason"] == "disabled"


@pytest.mark.parametrize("fault", ["missing", "extra", "nan", "wrong_model"])
def test_atomic_protocol_rejects_malformed_answers(tmp_path, fault):
    snap, basis, _, baseline = setup(tmp_path)
    request, domains = build_request(snap, basis, "v1")
    response = reply(request, baseline)
    name = next(k for k in domains if k.startswith("evidence_"))
    if fault == "missing":
        response["answers"].pop(name)
    elif fault == "extra":
        response["answers"]["unexpected"] = response["answers"][name]
    elif fault == "nan":
        response["answers"][name]["probabilities"]["sufficient"] = float("nan")
    else:
        response["model"] = "unrequested"
    with pytest.raises(ValueError):
        decode_order(response, snap, domains, "v1")


def test_policy_switch_has_separate_reservation_and_response(tmp_path):
    snap, basis, guard, baseline = setup(tmp_path)
    initialize_run(tmp_path / "run", 2)
    store = RunStore(tmp_path / "run")
    calls = []

    def transport(request, *args):
        calls.append(request)
        return {"response": reply(request, baseline)}

    records = [
        assess_one(
            snap,
            basis,
            Config(
                mode="assist",
                model="v1",
                allow_egress=True,
                ranking_policy=policy,
                max_requests_per_run=2,
            ),
            store,
            guard,
            transport,
            lambda: "fixture",
        )
        for policy in ["pairwise", "evidence_atomic"]
    ]
    assert len(calls) == 2
    assert all(r["status"] == "completed" for r in records)
    assert records[0]["request_id"] != records[1]["request_id"]


def test_evidence_mutation_during_request_cannot_be_adopted(tmp_path):
    snap, basis, guard, baseline = setup(tmp_path)
    initialize_run(tmp_path / "run", 1)

    def transport(request, *args):
        (tmp_path / "observed.txt").write_text("source changed during provider call")
        return {"response": reply(request, baseline)}

    result = assess_one(
        snap,
        basis,
        Config(
            mode="assist",
            model="v1",
            allow_egress=True,
            ranking_policy="evidence_atomic",
        ),
        RunStore(tmp_path / "run"),
        guard,
        transport,
        lambda: "fixture",
    )
    assert result["status"] == "stale" and result["order"] is None
