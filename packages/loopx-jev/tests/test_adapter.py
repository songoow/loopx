"""Offline transport/ordering/concurrency boundaries; not Jev quality evidence."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import copy
import json
import multiprocessing
from pathlib import Path
import threading
import time

import pytest

from loopx.control_plane.ranking_context import ranking_context, preference_for, snapshot_id, ranking_active, validate_preference
from loopx_jev.config import Config, load_config, strict_json
from loopx_jev.protocol import build_request, decode_order
from loopx_jev.runner import assess_all, assess_one, read_basis
from loopx_jev.store import RunStore, initialize_run
from loopx_jev.transport import TransportFailure
from loopx_jev.cli import execute

BASIS = {"goal_id": "g", "objective": "Verified legacy compatibility", "acceptance": ["An independent legacy fixture passes."]}


def snap(ids=("a", "b", "c")):
    return {"scenario": "todo_order", "baseline_order": list(ids), "cohorts": [list(ids)],
            "cards": [{"id": x, "todo": {"title": x, "text": "Test " + x}} for x in ids],
            "source": {"revision": 1}}


def response(request, choices=None):
    labels = ["left", "right", "tie", "insufficient_evidence"]
    answers = {}
    for i, name in enumerate(request["questions"]):
        chosen = choices[i] if choices else "right"
        answers[name] = {"type": "choice", "choice": chosen,
                         "probabilities": {key: float(key == chosen) for key in labels}, "confidence": 1.0}
    return {"model": request["model"], "answers": answers, "usage": {"input_tokens": 10, "output_tokens": 0}}


def config():
    return Config(mode="assist", model="fixture-pinned-v1", allow_egress=True, generation="fixture")


def store(tmp_path, maximum=20):
    root = tmp_path / "run"
    initialize_run(root, maximum)
    return RunStore(root)


@pytest.mark.parametrize("raw", ['{"mode":"off","mode":"assist"}', '{"x":NaN}', '{"x":Infinity}'])
def test_strict_json_rejects_ambiguous_values(raw):
    with pytest.raises(ValueError): strict_json(raw)


@pytest.mark.parametrize("patch", [
    {"mode": "on"}, {"allow_egress": "true"}, {"model": "jev-latest", "mode": "assist"},
    {"limits": {"max_parallel": True}}, {"limits": {"max_candidates": 7}},
    {"new_global_permission": True}, {"scenarios": ["todo_order", "todo_order"]},
    {"minimum_preference_probability": 1.2},
])
def test_invalid_configuration(tmp_path, patch):
    path=tmp_path/'config.json';path.write_text(json.dumps({"schema_version":"loopx_jev_branch_config_v0", **patch}))
    with pytest.raises((TypeError, ValueError)): load_config(path)


def test_off_wrapper_does_not_read_optional_inputs_or_credentials(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs): raise AssertionError("optional boundary was used while off")
    monkeypatch.setenv("TYPESAFE_API_KEY", "fixture-only")
    missing = tmp_path/'does-not-exist'
    called=[]
    assert execute(["quota", "should-run", "--goal-id", "g"], config_path=None,
                   capture_path=missing,basis_path=missing,run_dir=missing,report_path=missing,
                   invoke=lambda argv: called.append(argv) or 0, transport=forbidden, credential=forbidden)==0
    assert len(called)==1 and not missing.exists()


@pytest.mark.parametrize("alter", [
    lambda r: r['answers'].pop('pair_0'),
    lambda r: r.update(model='moving-alias'),
    lambda r: r['answers']['pair_0'].update(type='unknown'),
    lambda r: r['answers']['pair_0']['probabilities'].update(left=float('nan')),
    lambda r: r['answers']['pair_0']['probabilities'].update(left=True),
    lambda r: r['answers']['pair_0']['probabilities'].update(other=0),
    lambda r: r['answers']['pair_0'].update(choice='unknown'),
    lambda r: r['answers']['pair_0'].update(confidence=float('inf')),
])
def test_exact_response_boundary(alter):
    s=snap();request,pairs=build_request(s,BASIS,'fixture-v1'); r=response(request)
    alter(r)
    with pytest.raises(ValueError):decode_order(r,s,pairs,'fixture-v1')


@pytest.mark.parametrize('choices',[
    ['left','right','left'], # a>b, c>a, b>c: a strict cycle
    ['tie','left','right'], # a=b but a>c and c>b
    ['left','insufficient_evidence','left'],
])
def test_cycles_contradictory_ties_and_abstention_fall_back(choices):
    s=snap();r,pairs=build_request(s,BASIS,'v1')
    with pytest.raises(ValueError):decode_order(response(r,choices),s,pairs,'v1')


def test_ties_keep_stable_baseline_and_reversed_pairs_reorder():
    s=snap(('c','b','a')); r,p=build_request(s,BASIS,'v1')
    assert decode_order(response(r,['tie']*3),s,p,'v1')==('c','b','a')
    assert decode_order(response(r,['left']*3),s,p,'v1')==('a','b','c')


def test_policy_groups_cannot_cross_even_with_exact_permutation():
    s=snap();s['cohorts']=[['a'],['b','c']]
    with pytest.raises(ValueError,match='cohort'):validate_preference(s,['b','a','c'])
    with ranking_context(preferences={snapshot_id(s):['b','a','c']}) as ctx:
        assert preference_for(s) is None
    assert ctx.events[-1]['status']=='invalid_preference_or_snapshot'


def test_context_isolation_and_revocation():
    s=snap();identity=snapshot_id(s)
    assert not ranking_active()
    with ranking_context(preferences={identity:['c','b','a']},guard=lambda:False):
        assert preference_for(s) is None
        with ranking_context(preferences={identity:['c','b','a']}):
            assert preference_for(s)==('c','b','a')
        assert preference_for(s) is None
        with ThreadPoolExecutor(1) as pool: assert pool.submit(ranking_active).result() is False
    assert not ranking_active()


def test_snapshot_mutation_cannot_consume_old_preference():
    s=snap();identity=snapshot_id(s)
    with ranking_context(preferences={identity:['c','b','a']}) as ctx:
        s['source']['revision']=2
        assert preference_for(s) is None
    assert ctx.events[-1]['status']=='baseline'


@pytest.mark.parametrize('change,reason',[(dict(mode='off'),'disabled'),(dict(allow_egress=False),'egress_denied')])
def test_disabled_or_denied_has_no_store_or_key_access(tmp_path,change,reason):
    class Forbidden:
        def reserve(self,*args):raise AssertionError('store touched')
    def forbidden():raise AssertionError('key touched')
    result=assess_one(snap(),BASIS,replace(config(),**change),Forbidden(),lambda:True,credential=forbidden)
    assert result['reason']==reason and result['dispatch']=='not_sent'


def test_duplicate_concurrent_requests_send_once(tmp_path):
    ledger=store(tmp_path);count=[];lock=threading.Lock()
    def transport(request,c,key):
        with lock:count.append(1)
        time.sleep(.05)
        return {'response':response(request)}
    with ThreadPoolExecutor(8) as pool:
        results=list(pool.map(lambda _:assess_one(snap(),BASIS,config(),ledger,lambda:True,transport,lambda:'fixture'), range(8)))
    assert len(count)==1
    assert sum(r['status']=='completed' for r in results)>=1
    again=assess_one(snap(),BASIS,config(),ledger,lambda:True,transport,lambda:'fixture')
    assert again['replayed'] and again['status']=='completed' and len(count)==1


def _reserve_process(root,identity,queue):
    queue.put(RunStore(Path(root)).reserve(identity,1) is None)


def test_two_processes_share_finite_attempt_budget(tmp_path):
    ledger=store(tmp_path,1);ctx=multiprocessing.get_context('spawn');queue=ctx.Queue()
    processes=[ctx.Process(target=_reserve_process,args=(str(ledger.root),str(i)*64,queue)) for i in (1,2)]
    for process in processes:process.start()
    outcomes=[queue.get(timeout=20) for _ in processes]
    for process in processes:process.join(20);assert process.exitcode==0
    assert sorted(outcomes)==[False,True]


def test_expired_result_keeps_no_resend_tombstone(tmp_path):
    ledger=store(tmp_path);calls=[]
    def transport(request,c,key):calls.append(1);return {'response':response(request)}
    r=assess_one(snap(),BASIS,config(),ledger,lambda:True,transport,lambda:'fixture')
    (ledger.root/(r['request_id']+'.json')).unlink()
    again=assess_one(snap(),BASIS,config(),ledger,lambda:True,transport,lambda:'fixture')
    assert again['reason']=='prior_attempt_unresolved' and len(calls)==1
    with pytest.raises(ValueError):initialize_run(ledger.root)


def test_failure_does_not_retry_or_claim_zero_cost(tmp_path):
    ledger=store(tmp_path);calls=[]
    def transport(*args):calls.append(1);raise TransportFailure('timeout')
    r=assess_one(snap(),BASIS,config(),ledger,lambda:True,transport,lambda:'fixture')
    assert r['status']=='failed' and r['dispatch']=='may_have_been_sent' and r['cost_usd'] is None
    assess_one(snap(),BASIS,config(),ledger,lambda:True,transport,lambda:'fixture')
    assert len(calls)==1


def test_revoked_inflight_response_not_used(tmp_path):
    ledger=store(tmp_path);active=[True]
    def transport(request,c,key):active[0]=False;return {'response':response(request)}
    r=assess_one(snap(),BASIS,config(),ledger,lambda:active[0],transport,lambda:'fixture')
    assert r['status']=='stale' and r['order'] is None


def test_parallel_distinct_requests_are_bounded_and_real(tmp_path):
    ledger=store(tmp_path);active=0;peak=0;lock=threading.Lock()
    def transport(request,c,key):
        nonlocal active,peak
        with lock:active+=1;peak=max(active,peak)
        time.sleep(.08)
        with lock:active-=1
        return {'response':response(request)}
    snapshots={}
    for i in range(5):
        s=snap();s['source']['revision']=i;snapshots[snapshot_id(s)]=s
    results=assess_all(snapshots,BASIS,config(),ledger,lambda:True,transport,lambda:'fixture')
    assert all(r['status']=='completed' for r in results) and peak==2


def test_evidence_is_host_read_and_version_guarded(tmp_path):
    evidence=tmp_path/'artifact.txt';evidence.write_text('original')
    basis=tmp_path/'basis.json';basis.write_text(json.dumps({**BASIS,'evidence':[{'ref':'artifact.txt'}]}))
    material,current=read_basis(basis,tmp_path)
    assert material['evidence'][0]['origin']=='host_file_read' and current()
    evidence.write_text('changed');assert not current()
    basis.write_text(json.dumps({**BASIS,'evidence':[{'ref':'../outside'}]}))
    with pytest.raises(ValueError):read_basis(basis,tmp_path)


def test_no_baseline_order_or_scoring_in_provider_request():
    s=snap();s['cards'][0]['todo'].update(index=999,confidence=1,score=500,suggested_commands=['bad'])
    request,_=build_request(s,BASIS,'v1');raw=json.dumps(request)
    assert 'suggested_commands' not in raw and 'baseline_order' not in raw and '999' not in raw


def test_optional_store_failure_never_sends_or_overrides(tmp_path):
    class Broken:
        def reserve(self,*args):raise OSError('private path should not be reflected')
    r=assess_one(snap(),BASIS,config(),Broken(),lambda:True,
                 lambda *args:pytest.fail('must not send'),lambda:'fixture')
    assert r['reason']=='attempt_store_unavailable' and r['dispatch']=='not_sent'


def test_provider_extra_text_never_persisted(tmp_path):
    ledger=store(tmp_path)
    def transport(request,c,key):
        r=response(request);r['answers']['pair_0']['explanation']='untrusted reflected content'
        return {'response':r}
    result=assess_one(snap(),BASIS,config(),ledger,lambda:True,transport,lambda:'fixture')
    assert result['status']=='completed'
    assert 'reflected content' not in json.dumps(result)
    assert 'reflected content' not in (ledger.root/(result['request_id']+'.json')).read_text()


def test_new_wrapper_never_accepts_command_name_embedded_in_other_arguments():
    from loopx_jev.cli import _arguments
    with pytest.raises(ValueError):_arguments(['todo','delete','quota','should-run'])
    with pytest.raises(ValueError):_arguments(['--registry','quota','todo','delete','quota','should-run'])
    assert _arguments(['--format=json','quota','should-run'])==['--format=json','quota','should-run']


def test_http_deadline_kills_worker_and_key_is_not_in_argv(monkeypatch):
    import subprocess
    from loopx_jev import transport
    observed={}
    class Slow:
        returncode=-9
        def communicate(self,data=None,timeout=None):
            if timeout is not None:raise subprocess.TimeoutExpired('worker',timeout)
            return b'',None
        def kill(self):observed['killed']=True
    def popen(argv,**kwargs):observed['argv']=argv;observed['environment']=kwargs['env'];return Slow()
    monkeypatch.setattr(transport.subprocess,'Popen',popen)
    with pytest.raises(TransportFailure,match='deadline_exceeded'):
        transport.send({'state':{},'questions':{}},config(),'fixture-secret-not-to-log')
    assert observed['killed']
    assert 'fixture-secret-not-to-log' not in str(observed)
    assert 'TYPESAFE_API_KEY' not in observed['environment']


def test_complete_abstention_is_not_a_transport_failure(tmp_path):
    ledger=store(tmp_path)
    def transport(request,c,key):return {'response':response(request,['insufficient_evidence']*len(request['questions']))}
    r=assess_one(snap(),BASIS,config(),ledger,lambda:True,transport,lambda:'fixture')
    assert r['status']=='abstained' and r['order'] is None and r['dispatch']=='response_received'
    assert r['usage']=={'input_tokens':10,'output_tokens':0}
    r2=assess_one(snap(),BASIS,config(),ledger,lambda:True,lambda *args:pytest.fail('no repeat'),lambda:'fixture')
    assert r2['status']=='abstained' and r2['replayed']


@pytest.mark.parametrize('payload,accepted', [
    (b'{"model":"v1","answers":{}}', True),
    (b'{"model":"v1","model":"v2","answers":{}}', False),
    (b'{"answers":{"pair_0":{"choice":"left","choice":"right"}}}', False),
    (b'{"usage":{"input_tokens":NaN}}', False),
])
def test_http_worker_preserves_ambiguous_provider_bytes_for_strict_validation(monkeypatch, payload, accepted):
    import io
    from loopx_jev import http_worker, transport
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, limit): return payload[:limit]
    class Opener:
        def open(self, *args, **kwargs): return Response()
    monkeypatch.setattr(http_worker.urllib.request, 'build_opener', lambda *args: Opener())
    class Child:
        returncode = 0
        def communicate(self, envelope, timeout):
            source = io.TextIOWrapper(io.BytesIO(envelope))
            target = io.TextIOWrapper(io.BytesIO())
            with monkeypatch.context() as local:
                local.setattr(http_worker.sys, 'stdin', source)
                local.setattr(http_worker.sys, 'stdout', target)
                http_worker.main()
                target.flush()
                output = target.buffer.getvalue()
            return output, None
    monkeypatch.setattr(transport.subprocess, 'Popen', lambda *args, **kwargs: Child())
    if accepted:
        result = transport.send({'state': {}, 'questions': {}}, config(), 'fixture')
        assert result['response'] == {'model': 'v1', 'answers': {}}
    else:
        with pytest.raises(TransportFailure, match='invalid_transport_response'):
            transport.send({'state': {}, 'questions': {}}, config(), 'fixture')


def test_deadline_includes_worker_spawn_before_sending_credential(monkeypatch):
    from loopx_jev import transport
    ticks = iter([0, 1, 200_000_000, 200_000_001])
    monkeypatch.setattr(transport.time, 'perf_counter_ns', lambda: next(ticks))
    observed = []
    class Child:
        def kill(self):observed.append('killed')
        def communicate(self, *args, **kwargs):
            assert not args, 'expired request must not send its credential envelope'
            return b'', None
    monkeypatch.setattr(transport.subprocess, 'Popen', lambda *a, **k: Child())
    with pytest.raises(TransportFailure, match='deadline_exceeded'):
        transport.send({'state': {}, 'questions': {}}, replace(config(), deadline_ms=100), 'fixture')
    assert observed == ['killed']
