"""D7 original TS owner and full quota CLI with real File/SQLite sources."""
import contextlib
from dataclasses import replace
import io
import json
from pathlib import Path

import pytest

from loopx.control_plane.ranking_context import ranking_context,snapshot_id
from loopx_jev.demo import select_todo,todo_inputs,fixture_response
from loopx_jev.cli import capture,execute,_original
from loopx_jev.store import initialize_run
from canonical_authority_fixture import initialize_canonical_authority,isolate_sqlite_runtime
from loopx.control_plane.coordination.runtime_shadow import build_runtime_shadow_source_snapshot
from loopx.control_plane.coordination.local_authority import read_canonical_todos_if_promoted
from loopx.control_plane.testing.canary_harness import write_fixture_registry


def test_real_selector_consumes_exact_preference_and_preserves_gate():
    with ranking_context() as ctx:assert select_todo()=='todo_polish'
    identity,snapshot=next(iter(ctx.snapshots.items()))
    assert snapshot['baseline_order']==['todo_polish','todo_fixture']
    assert 'todo_publish' not in snapshot['baseline_order']
    with ranking_context(preferences={identity:['todo_fixture','todo_polish']}) as applied:
        assert select_todo()=='todo_fixture'
    assert any(e['status']=='preference_consumed' for e in applied.events)


def _setup(tmp_path,monkeypatch,provider):
    if provider=='sqlite':isolate_sqlite_runtime(tmp_path,monkeypatch)
    state=tmp_path/'STATE.md';runtime=tmp_path/'runtime';registry=tmp_path/'registry.json'
    state.write_text(
        '# Goal\n\n## Agent Todo\n\n'
        '- [ ] [P1] Polish existing diagnostic wording\n'
        '  <!-- loopx:todo todo_id=todo_polish role=agent status=open task_class=advancement_task claimed_by=agent-a action_kind=inspect_report -->\n'
        '- [ ] [P1] Build an independent legacy fixture\n'
        '  <!-- loopx:todo todo_id=todo_fixture role=agent status=open task_class=advancement_task claimed_by=agent-a action_kind=inspect_report -->\n'
        '- [ ] [P0] Publish report\n'
        '  <!-- loopx:todo todo_id=todo_publish role=agent status=open task_class=advancement_task claimed_by=agent-a action_kind=publish_report -->\n'
        '\n## User Todo / Owner Review Reading Queue\n\n'
        '- [ ] Review publication\n'
        '  <!-- loopx:todo todo_id=todo_gate role=user status=open task_class=user_gate blocks_agent=agent-a action_kind=publish_report unblocks_todo_id=todo_publish -->\n')
    write_fixture_registry(project=tmp_path,runtime_root=runtime,registry_path=registry,goal_id='goal-a',domain='software',
                           adapter_kind='generic_project_goal_v0',state_file=str(state),registered_agents=['agent-a'],quota_allowed_slots=None)
    if provider!='markdown':
        goal=json.loads(registry.read_text())['goals'][0]
        projection,_=build_runtime_shadow_source_snapshot(goal=goal,runtime_root=runtime,state_path=state,registry_path=registry)
        initialize_canonical_authority(runtime,'goal-a',projection,state_path=state,provider=provider)
        state.unlink()
    args=['--format','json','--registry',str(registry),'--runtime-root',str(runtime),'quota','should-run',
          '--goal-id','goal-a','--agent-id','agent-a','--scan-path',str(tmp_path)]
    return args,state,runtime,registry


@pytest.mark.parametrize('provider',['markdown','file','sqlite'])
@pytest.mark.parametrize('mode',['off','shadow','assist'])
@pytest.mark.parametrize('policy',['pairwise','evidence_atomic','single_choice'])
def test_actual_quota_cli_and_real_authority(tmp_path,monkeypatch,provider,mode,policy):
    monkeypatch.chdir(tmp_path)
    args,state,runtime,registry=_setup(tmp_path,monkeypatch,provider)
    capture_file=tmp_path/'capture.json'; config_file=tmp_path/'jev.json'; basis_file=tmp_path/'basis.json'
    config_file.write_text(json.dumps({'schema_version':'loopx_jev_branch_config_v0','mode':mode,
                                      'model':'fixture-v1','allow_egress':True}))
    basis_file.write_text(json.dumps({'goal_id':'goal-a','objective':'Verified legacy compatibility',
                                     'acceptance':['independent fixture exists']}))
    run=tmp_path/'run';initialize_run(run,10)
    packets=[]
    def invoke(argv):
        out=io.StringIO()
        with contextlib.redirect_stdout(out):code=_original(argv)
        packets.append(json.loads(out.getvalue()))
        return code
    assert capture(args,capture_file,invoke=invoke)==0
    captured=json.loads(capture_file.read_text())
    assert captured['snapshots'], 'actual quota path must reach the owner capture, not a fabricated snapshot'
    if policy == 'evidence_atomic':
        from atomic_ranking_fixture import bind_atomic_evidence
        bind_atomic_evidence(tmp_path, config_file, capture_file, basis_file)
    if policy == 'single_choice':
        from single_choice_fixture import bind_single_choice
        bind_single_choice(config_file)
    before=state.read_bytes() if state.exists() else None
    authority_before=read_canonical_todos_if_promoted(runtime_root=runtime,goal_id='goal-a')
    calls=[]
    def transport(*arguments):
        calls.append(1)
        if policy == 'evidence_atomic':
            from atomic_ranking_fixture import atomic_response
            return atomic_response(*arguments)
        if policy == 'single_choice':
            from single_choice_fixture import single_choice_response
            return single_choice_response(*arguments)
        return fixture_response(*arguments)
    assert execute(args,config_path=config_file,capture_path=capture_file,basis_path=basis_file,run_dir=run,
                   report_path=tmp_path/'report.json',invoke=invoke,transport=transport,credential=lambda:'fixture')==0
    packet=packets[-1]
    expected='todo_fixture' if mode=='assist' else 'todo_polish'
    assert packet['scoped_user_gate_fallback']['selected_executable']['todo_id']==expected,packet
    assert packet['requires_user_action'] is True
    assert packet['scoped_user_gate_fallback']['blocked_agent_items'][0]['todo_id']=='todo_publish'
    assert (state.read_bytes() if state.exists() else None)==before
    assert read_canonical_todos_if_promoted(runtime_root=runtime,goal_id='goal-a')==authority_before
    assert bool(calls)==(mode!='off')
    assert (tmp_path/'report.json').exists()==(mode!='off')


def test_stale_owner_facts_decline_old_order():
    from loopx.control_plane.todos.decision_scope import select_scoped_gate_fallback
    gates,todos=todo_inputs()
    kwargs=dict(agent_id='agent-a', allow_unrelated_gate=True, monitor_debt_backoff_active=False)
    with ranking_context() as ctx:select_scoped_gate_fallback(gates,todos,**kwargs)
    identity,snapshot=next(iter(ctx.snapshots.items()))
    # The exact current source includes the policy-affecting gate. No stale reuse.
    kwargs['monitor_debt_backoff_active']=True
    with ranking_context(preferences={identity:list(reversed(snapshot['baseline_order']))}) as current:
        result=select_scoped_gate_fallback(gates,todos,**kwargs)
    assert todos[result['selected_index']]['todo_id']=='todo_polish'
    assert not any(e['status']=='preference_consumed' for e in current.events)

@pytest.mark.parametrize('provider',['file','sqlite'])
@pytest.mark.parametrize('mode',['off','assist'])
def test_selected_todo_reaches_real_independent_validation_and_completion(tmp_path,monkeypatch,provider,mode):
    """Jev is injected; selection, subprocess, validator and canonical completion are real."""
    import subprocess
    import sys
    from loopx.control_plane.testing.canary_harness import run_json_cli_result
    monkeypatch.chdir(tmp_path)
    args,state,runtime,registry=_setup(tmp_path,monkeypatch,provider)
    def original(*arguments):
        return run_json_cli_result(*arguments,registry_path=registry,runtime_root=runtime)
    acceptance={
        'objective':'Produce independently checked legacy evidence without releasing anything',
        'non_goals':['No publication'],
        'criteria':[
            {'id':'legacy','description':'The legacy fixture contains the exact independent value',
             'validation_argv':[sys.executable,'-c',"import json;from pathlib import Path;assert json.loads(Path('legacy.json').read_text()) == {'version':0,'name':'legacy'}"],
             'validation_timeout_seconds':5},
            {'id':'wording','description':'The diagnostic text was written',
             'validation_argv':[sys.executable,'-c',"from pathlib import Path;assert Path('diagnostic.txt').read_text() == 'Repaired wording'"],
             'validation_timeout_seconds':5}],
        'bindings':[{'todo_id':'todo_fixture','criterion_ids':['legacy']},{'todo_id':'todo_polish','criterion_ids':['wording']}],
    }
    doc=tmp_path/'acceptance.json';doc.write_text(json.dumps(acceptance))
    code,inspected=original('goal-acceptance','inspect','--goal-id','goal-a');assert code==0,inspected
    code,configured=original('goal-acceptance','configure','--goal-id','goal-a','--document',str(doc),
                            '--expected-provider-revision',inspected['provider_revision'],'--execute')
    assert code==0,configured
    config_file=tmp_path/'jev.json';config_file.write_text(json.dumps({'schema_version':'loopx_jev_branch_config_v0',
                                'mode':mode,'model':'fixture-v1','allow_egress':True}))
    basis=tmp_path/'basis.json';basis.write_text(json.dumps({'goal_id':'goal-a','objective':acceptance['objective'],
                       'acceptance':[x['description'] for x in acceptance['criteria']], 'evidence':[{'ref':'acceptance.json'}]}))
    captured=tmp_path/'capture.json';packets=[]
    def invoke(argv):
        stream=io.StringIO()
        with contextlib.redirect_stdout(stream):code=_original(argv)
        packets.append(json.loads(stream.getvalue()));return code
    assert capture(args,captured,invoke)==0
    run=tmp_path/'run';initialize_run(run)
    assert execute(args,config_path=config_file,capture_path=captured,basis_path=basis,run_dir=run,
                   report_path=tmp_path/'report.json',invoke=invoke,transport=fixture_response,credential=lambda:'fixture')==0
    selected=packets[-1]['scoped_user_gate_fallback']['selected_executable']['todo_id']
    expected='todo_fixture' if mode=='assist' else 'todo_polish';assert selected==expected
    complete=['todo','complete','--todo-id',selected,'--goal-id','goal-a','--agent-id','agent-a']
    code,refusal=original(*complete)
    assert code==1 and refusal['reason_code']=='goal_acceptance_validation_rejected',refusal
    # Synthetic coding host; it has no ability to forge the independent check or receipt.
    script="""import json,sys
from pathlib import Path
if sys.argv[1]=='todo_fixture':Path('legacy.json').write_text(json.dumps({'version':0,'name':'legacy'}))
else:Path('diagnostic.txt').write_text('Repaired wording')
"""
    subprocess.run([sys.executable,'-c',script,selected],cwd=tmp_path,check=True,timeout=10)
    code,done=original(*complete)
    assert code==0 and done['changed'] is True,done
    assert done['goal_acceptance_completion']['source_binding']['todo_id']==selected
    assert done['goal_acceptance_completion']['results'][0]['passed'] is True
    # Canonical state and the public completion readback agree. No publication occurred.
    code,readback=original('goal-acceptance','inspect','--goal-id','goal-a')
    assert code==0
    assert json.loads(registry.read_text())['goals'][0]['status']=='active'
    assert not (tmp_path/'published').exists()

@pytest.mark.parametrize('failure',['timeout','disable','changed_state','same_order'])
def test_actual_cli_fallback_and_disable_boundaries(tmp_path,monkeypatch,failure):
    from loopx_jev.transport import TransportFailure
    monkeypatch.chdir(tmp_path)
    args,state,runtime,registry=_setup(tmp_path,monkeypatch,'markdown')
    conf={'schema_version':'loopx_jev_branch_config_v0','mode':'assist','model':'fixture-v1','allow_egress':True}
    config=tmp_path/'config.json';config.write_text(json.dumps(conf))
    basis=tmp_path/'basis.json';basis.write_text(json.dumps({'goal_id':'goal-a','objective':'Compatibility evidence','acceptance':['legacy sample']}))
    cap=tmp_path/'cap.json';run=tmp_path/'run';report=tmp_path/'report.json';initialize_run(run)
    packets=[]
    def invoke(argv):
        output=io.StringIO()
        with contextlib.redirect_stdout(output):code=_original(argv)
        packets.append(json.loads(output.getvalue()));return code
    assert capture(args,cap,invoke)==0
    def transport(request,c,key):
        if failure=='timeout':raise TransportFailure('deadline_exceeded')
        if failure=='disable':config.write_text(json.dumps({**conf,'mode':'off'}))
        if failure=='changed_state':state.write_text(state.read_text().replace('Polish existing diagnostic wording','Polish updated diagnostic wording'))
        result=fixture_response(request,c,key)
        if failure=='same_order':
            for answer in result['response']['answers'].values():
                answer['choice']='right' # sorted IDs: fixture on left, polish on right
                answer['probabilities']={k:float(k=='right') for k in answer['probabilities']}
        return result
    assert execute(args,config_path=config,capture_path=cap,basis_path=basis,run_dir=run,report_path=report,
                   invoke=invoke,transport=transport,credential=lambda:'fixture')==0
    assert packets[-1]['scoped_user_gate_fallback']['selected_executable']['todo_id']=='todo_polish'
    assert packets[-1]['requires_user_action'] is True
    evidence=json.loads(report.read_text())
    if failure=='changed_state':
        assert not any(e['status']=='preference_consumed' for e in evidence['consumption'])
    if failure=='disable':assert evidence['assessments'][0]['status']=='stale'
    if failure=='timeout':assert evidence['assessments'][0]['cost_usd'] is None
