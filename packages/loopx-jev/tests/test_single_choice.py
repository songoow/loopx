"""single_choice: one Choice per cohort, cohorts decided independently, no forced total order."""

import pytest

from loopx.control_plane.ranking_context import ranking_context
from loopx_jev.config import load_config
from loopx_jev.demo import select_todo, plan_explore
from loopx_jev.protocol import PreferenceUnavailable
from loopx_jev.single_choice import ABSTAIN, build_request, decode_order

BASIS = {"objective": "Obtain new independent evidence", "acceptance": ["independent check passes"]}


def snap(cohorts, cards=None):
    ids = [c for group in cohorts for c in group]
    return {"scenario": "todo_order", "owner": "t", "source": {}, "baseline_order": ids,
            "cohorts": cohorts, "cards": cards or [{"id": i, "todo": {"title": i}} for i in ids]}


def answer(request, picks, probability=1.0):
    answers = {}
    for name, question in request["questions"].items():
        labels = list(question["criteria"])
        choice = picks.get(name, ABSTAIN)
        rest = (1 - probability) / (len(labels) - 1)
        answers[name] = {"type": "choice", "choice": choice,
                         "probabilities": {v: probability if v == choice else rest for v in labels}}
    return {"model": request["model"], "answers": answers}


def test_one_question_per_cohort_lists_every_member_plus_abstain():
    request, domains = build_request(snap([["a", "b", "c"], ["d", "e"], ["f"]]), BASIS, "m")
    assert set(domains) == {"cohort_0", "cohort_1"}, "singleton cohorts ask nothing"
    assert set(request["questions"]["cohort_0"]["criteria"]) == {"a", "b", "c", ABSTAIN}
    assert set(request["questions"]["cohort_1"]["criteria"]) == {"d", "e", ABSTAIN}
    assert [c["id"] for c in request["state"]["cards"]] == sorted("abcdef"), "presentation independent of baseline order"


def test_winner_moves_to_its_cohort_front_and_other_cohorts_keep_baseline():
    s = snap([["a", "b", "c"], ["d", "e"]])
    request, domains = build_request(s, BASIS, "m")
    order = decode_order(answer(request, {"cohort_0": "c"}), s, domains, "m")
    assert order == ("c", "a", "b", "d", "e")


def test_undecided_tail_does_not_discard_a_clear_cohort_decision():
    s = snap([["a", "b"], ["c", "d"]])
    request, domains = build_request(s, BASIS, "m")
    response = answer(request, {"cohort_0": "b", "cohort_1": "d"})
    response["answers"]["cohort_1"]["probabilities"] = {"c": 0.45, "d": 0.5, ABSTAIN: 0.05}
    assert decode_order(response, s, domains, "m") == ("b", "a", "c", "d")


@pytest.mark.parametrize("probability", [0.59, 0.3])
def test_low_peak_probability_abstains(probability):
    s = snap([["a", "b", "c"]])
    request, domains = build_request(s, BASIS, "m")
    with pytest.raises(PreferenceUnavailable):
        decode_order(answer(request, {"cohort_0": "b"}, probability), s, domains, "m")


def test_explicit_abstain_label_abstains_even_at_full_probability():
    s = snap([["a", "b"]])
    request, domains = build_request(s, BASIS, "m")
    with pytest.raises(PreferenceUnavailable):
        decode_order(answer(request, {}), s, domains, "m")


def test_foreign_label_or_missing_answer_is_rejected_not_adopted():
    s = snap([["a", "b"]])
    request, domains = build_request(s, BASIS, "m")
    response = answer(request, {"cohort_0": "a"})
    response["answers"]["cohort_0"]["probabilities"]["zzz"] = 0.0
    with pytest.raises(ValueError):
        decode_order(response, s, domains, "m")
    with pytest.raises(ValueError):
        decode_order({"model": "m", "answers": {}}, s, domains, "m")
    with pytest.raises(ValueError):
        decode_order(answer(request, {"cohort_0": "a"}), s, domains, "other-model")


def test_candidate_id_equal_to_abstain_label_is_refused():
    with pytest.raises(ValueError):
        build_request(snap([["a", ABSTAIN]]), BASIS, "m")


def test_config_accepts_policy(tmp_path):
    path = tmp_path / "c.json"
    path.write_text('{"schema_version":"loopx_jev_branch_config_v0","mode":"assist","model":"jev-1.13.0","allow_egress":true,"ranking_policy":"single_choice"}')
    assert load_config(path).ranking_policy == "single_choice"


@pytest.mark.parametrize("owner", [select_todo, lambda: plan_explore()["selected_worker_branches"][0]["branch_id"]], ids=["d7", "d8"])
def test_real_owner_snapshot_builds_a_single_question(owner):
    with ranking_context() as ctx:
        owner()
    s = next(iter(ctx.snapshots.values()))
    request, domains = build_request(s, BASIS, "m")
    assert len(domains) == 1
    assert set(request["questions"]["cohort_0"]["criteria"]) == set(s["baseline_order"]) | {ABSTAIN}
