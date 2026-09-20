"""Durable finite-advice boundaries; injected answers are not model-quality evidence."""
from dataclasses import replace
import copy
import json

import pytest

from loopx_jev.advisory import Direction, OWNERS, build_request, decode_assessment, validate_input
from loopx_jev.advisory_cli import assess
from loopx_jev.config import Config
from loopx_jev.runner import assess_one
from loopx_jev.store import RunStore, initialize_run

BASIS = {'goal_id': 'example', 'objective': 'Verify a compatible migration',
         'acceptance': ['Independent backend and compatibility evidence'],
         'evidence': [{'ref': 'evidence.txt', 'text': 'Only mocked SQLite results; the live backend was not tested.', 'origin': 'host_file_read'}]}
FACTS = {
    'progress_review': {'work_summary': 'Added an independent version zero fixture', 'history_available': True, 'work_state': 'working'},
    'owner_reuse': {'new_concept': 'job_state', 'intended_contract': 'Quota ownership lifecycle'},
    'claim_evidence': {'head_revision': 'revision-1'},
    'material_order': {'question': 'Was the live backend verified?'},
    'skill_suggestion': {'task': 'Review a source change without installing anything'},
    'replan_comparison': {'decision': 'Choose the next experiment', 'prior_outcomes': 'ASCII passed', 'constraints': 'One bounded experiment'},
}


def packet(direction):
    direction = Direction(direction)
    return {'schema': 'jev_advisory_input_v0', 'scenario': direction.value,
            'source': {'owner': OWNERS[direction], 'revision': 'revision-1'},
            'facts': copy.deepcopy(FACTS[direction.value]),
            'candidates': [] if direction == Direction.PROGRESS else [
                {'id': 'a', 'description': 'First candidate', 'evidence_refs': ['evidence.txt'], 'required': False},
                {'id': 'b', 'description': 'Second candidate', 'evidence_refs': ['evidence.txt'], 'required': True}]}


def response(request, choices=None):
    answers = {}
    for index, (name, question) in enumerate(request['questions'].items()):
        labels = list(question['criteria'])
        selected = choices[index] if choices else labels[0]
        answers[name] = {'type': 'choice', 'choice': selected, 'confidence': 1.,
                         'probabilities': {label: float(label == selected) for label in labels}}
    return {'model': request['model'], 'answers': answers}


@pytest.mark.parametrize('direction', list(Direction))
def test_real_assessment_engine_preserves_authority_and_no_second_dispatch(tmp_path, direction):
    snapshot = packet(direction); before = copy.deepcopy(snapshot)
    config = Config(mode='assist', scenarios=(direction,), model='fixture-v1', allow_egress=True)
    initialize_run(tmp_path/'run', 1); store = RunStore(tmp_path/'run'); calls = []
    def transport(request, config, key):
        calls.append(request)
        return {'response': response(request)}
    result = assess_one(snapshot, BASIS, config, store, lambda: True, transport, lambda: 'fixture')
    assert result['status'] == 'completed'
    assert result['order'] is None and result['assessment']['authority'] == 'advisory_only'
    again = assess_one(snapshot, BASIS, config, store, lambda: True, transport, lambda: 'fixture')
    assert again['replayed'] and again['cached_provider_measurements'] and len(calls) == 1
    assert snapshot == before
    assert all(isinstance(v, int) and v >= 0 for v in result['assessment_timing_ns'].values())


def test_progress_missing_history_and_wait_are_not_drift():
    s = packet('progress_review'); s['facts'].update(history_available=False, work_state='waiting')
    request, domains = build_request(s, BASIS, 'v1')
    actual = decode_assessment(response(request, ['necessary_prerequisite', 'new_evidence']), s, domains, 'v1')
    assert actual['judgments'] == {'relation': 'necessary_prerequisite', 'increment': 'unknown'}
    assert actual['work_state'] == 'waiting'
    with pytest.raises(ValueError, match='missing_observed_evidence'):
        build_request(s, {**BASIS, 'evidence': []}, 'v1')


def test_claims_without_evidence_are_unknown_even_if_model_says_supported():
    s = packet('claim_evidence');s['candidates'][0]['evidence_refs'] = []
    request, domains = build_request(s, BASIS, 'v1')
    result = decode_assessment(response(request), s, domains, 'v1')
    assert result['by_candidate']['a'] == 'insufficient_evidence'
    assert result['coverage'] == {'decided': 1, 'total': 2}
    s['facts']['head_revision'] = 'different-head'
    with pytest.raises(ValueError, match='claim_head_mismatch'):validate_input(s)


def test_material_order_keeps_mandatory_and_every_candidate():
    s = packet('material_order'); request, domains = build_request(s, BASIS, 'v1')
    result = decode_assessment(response(request, ['useful', 'not_useful']), s, domains, 'v1')
    assert result['order'] == ['b', 'a'] and result['required_ids'] == ['b']
    assert set(result['order']) == {c['id'] for c in s['candidates']}


@pytest.mark.parametrize('direction,choices,key,expected', [
    ('owner_reuse', ['related_distinct', 'unrelated'], 'by_candidate', {'a': 'related_distinct', 'b': 'unrelated'}),
    ('skill_suggestion', ['not_applicable', 'applicable'], 'suggested_ids', ['b']),
    ('replan_comparison', ['repeats_evidence', 'adds_evidence'], 'nonredundant_ids', ['b']),
])
def test_direction_specific_result_is_not_an_action(direction, choices, key, expected):
    s = packet(direction); request, domains = build_request(s, BASIS, 'v1')
    result = decode_assessment(response(request, choices), s, domains, 'v1')
    assert result[key] == expected and result['authority'] == 'advisory_only'
    assert not {'execute', 'install', 'commit', 'approved'} & result.keys()


@pytest.mark.parametrize('direction', list(Direction))
def test_unknown_answers_preserve_abstention(direction):
    s = packet(direction); request, domains = build_request(s, BASIS, 'v1')
    choices = [list(q['criteria'])[-1] for q in request['questions'].values()]
    result = decode_assessment(response(request, choices), s, domains, 'v1')
    assert result['coverage']['decided'] == 0


@pytest.mark.parametrize('mutation', [
    lambda s: s['source'].update(owner='invented'),
    lambda s: s['candidates'].append(copy.deepcopy(s['candidates'][0])),
    lambda s: s['candidates'][0].update(required='false'),
    lambda s: s['candidates'][0].update(evidence_refs=['not-read.txt']),
])
def test_bad_source_or_membership_rejected(mutation):
    s = packet('material_order');mutation(s)
    with pytest.raises(ValueError):build_request(s, BASIS, 'v1')


def test_assess_off_does_not_read_inputs_ledger_key_or_write(tmp_path, monkeypatch, capsys):
    def forbidden(*args, **kwargs): raise AssertionError('disabled boundary touched')
    monkeypatch.setattr('loopx_jev.advisory_cli.read_json', forbidden)
    missing = tmp_path/'missing'
    assert assess(missing, missing, None, missing, missing, transport=forbidden, credential=forbidden) == 0
    assert json.loads(capsys.readouterr().out)['status'] == 'disabled'
    assert not missing.exists()


@pytest.mark.parametrize('mode', ['shadow', 'assist'])
@pytest.mark.parametrize('stale', [False, True])
def test_explicit_assess_cli_readback_and_mid_request_revocation(tmp_path, monkeypatch, capsys, mode, stale):
    monkeypatch.chdir(tmp_path)
    (tmp_path/'evidence.txt').write_text('actual evidence')
    (tmp_path/'basis.json').write_text(json.dumps({**BASIS, 'evidence': [{'ref': 'evidence.txt'}]}))
    (tmp_path/'input.json').write_text(json.dumps(packet('skill_suggestion')))
    config = tmp_path/'config.json';config.write_text(json.dumps({'schema_version': 'loopx_jev_branch_config_v0',
        'mode': mode, 'scenarios': ['skill_suggestion'], 'model': 'fixture-v1', 'allow_egress': True}))
    initialize_run(tmp_path/'run', 1)
    def transport(request, *args):
        if stale:(tmp_path/'evidence.txt').write_text('changed evidence')
        return {'response': response(request)}
    code = assess(tmp_path/'input.json', tmp_path/'basis.json', config, tmp_path/'run', tmp_path/'report.json',
                  transport=transport, credential=lambda: 'fixture')
    receipt = json.loads(capsys.readouterr().out)
    report = json.loads((tmp_path/'report.json').read_text())
    assert code == (3 if stale else 0)
    assert (receipt['advice'] is not None) == (mode == 'assist' and not stale)
    assert report['fresh_at_readback'] == (not stale)
    assert receipt['timing_ns']['report_write'] > 0


def test_partial_coverage_retains_known_and_unknown_independently():
    s = packet('skill_suggestion'); request, domains = build_request(s, BASIS, 'v1')
    r = response(request, ['applicable', 'unknown'])
    result = decode_assessment(r, s, domains, 'v1')
    assert result['coverage'] == {'decided': 1, 'total': 2}
    assert result['suggested_ids'] == ['a']
    r['answers']['item_0']['probabilities'] = {'applicable': .5, 'not_applicable': .3, 'unknown': .2}
    result = decode_assessment(r, s, domains, 'v1')
    assert result['coverage']['decided'] == 0 and result['suggested_ids'] == []


def test_failed_transport_still_records_its_duration_and_never_returns_advice(tmp_path):
    from loopx_jev.transport import TransportFailure
    initialize_run(tmp_path/'run', 1)
    def fail(*args):raise TransportFailure('deadline_exceeded')
    result = assess_one(packet('skill_suggestion'), BASIS,
        Config(mode='assist', scenarios=('skill_suggestion',), model='v1', allow_egress=True),
        RunStore(tmp_path/'run'), lambda: True, fail, lambda: 'fixture')
    assert result['status'] == 'failed' and 'assessment' not in result
    assert result['assessment_timing_ns']['transport_inclusive'] >= 0
    assert result['assessment_total_ns'] >= sum(result['assessment_timing_ns'].values())


def test_shipped_examples_match_actual_input_contract():
    from pathlib import Path
    from loopx_jev.runner import read_basis
    example_root = Path(__file__).resolve().parents[1]/'examples/advisory'
    seen = set()
    for path in example_root.glob('D*/input.json'):
        snapshot = json.loads(path.read_text())
        material, current = read_basis(path.parent/'basis.json', path.parent)
        request, domains = build_request(snapshot, material, 'fixture-v1')
        assert request['questions'] and domains and current()
        seen.add(snapshot['scenario'])
    assert seen == set(Direction)


def test_off_cli_process_does_not_import_transport(tmp_path):
    import subprocess, sys
    script = '''import sys
from loopx_jev.cli import main
assert main(['assess','--input','missing','--basis','missing','--run-dir','missing','--report','missing']) == 0
assert 'loopx_jev.transport' not in sys.modules
'''
    result = subprocess.run([sys.executable, '-c', script], cwd=tmp_path, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert not list(tmp_path.iterdir())


def test_cached_advice_is_revoked_during_replay_readback(tmp_path):
    initialize_run(tmp_path/'run', 1);ledger = RunStore(tmp_path/'run')
    config = Config(mode='assist', scenarios=('skill_suggestion',), model='v1', allow_egress=True)
    def transport(request, *args): return {'response': response(request)}
    assert assess_one(packet('skill_suggestion'), BASIS, config, ledger, lambda: True, transport, lambda: 'fixture')['status'] == 'completed'
    checks = iter([True, False])
    result = assess_one(packet('skill_suggestion'), BASIS, config, ledger, lambda: next(checks),
                        lambda *args: pytest.fail('cached result must not resend'), lambda: 'fixture')
    assert result['status'] == 'stale' and result['reason'] == 'revoked_or_stale_on_replay'
    assert 'assessment' not in result
