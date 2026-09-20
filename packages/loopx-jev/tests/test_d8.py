"""D8 real planner/admission, no provider quality or actual cloud-run claims."""
import copy
import importlib.util
import os
from pathlib import Path
import types

import pytest

from loopx.control_plane.ranking_context import ranking_context,snapshot_id
from loopx.capabilities.explore.worker_branch_plan import build_explore_worker_branch_plan
from loopx_jev.demo import explore_inputs,plan_explore,run_demo


def test_original_planner_consumes_order_before_admission():
    with ranking_context() as ctx:baseline=plan_explore()
    identity,snapshot=next(iter(ctx.snapshots.items()))
    original=baseline['selected_worker_branches'][0]['branch_id']
    preferred=next(x for x in snapshot['baseline_order'] if 'unicode' in x)
    order=[preferred]+[x for x in snapshot['baseline_order'] if x!=preferred]
    before=copy.deepcopy(snapshot)
    with ranking_context(preferences={identity:order}) as applied:changed=plan_explore()
    assert changed['selected_worker_branches'][0]['branch_id']==preferred and preferred!=original
    assert snapshot==before
    current=next(iter(applied.snapshots.values()))
    original_cards={c['id']:c['branch'] for c in snapshot['cards']}
    for card in current['cards']:
        assert card['branch']==original_cards[card['id']]
    assert changed['boundary']==baseline['boundary']
    assert any(e['status']=='preference_consumed' for e in applied.events)


def test_disabled_explore_never_constructs_assessment_snapshot():
    kwargs=explore_inputs();kwargs['orchestration']={}
    with ranking_context() as ctx:result=build_explore_worker_branch_plan(**kwargs)
    assert result['enabled'] is False and ctx.snapshots=={}


def test_foreign_or_missing_candidate_cannot_get_admitted():
    with ranking_context() as ctx:baseline=plan_explore()
    identity,s=next(iter(ctx.snapshots.items()))
    for bad in [['invented']+s['baseline_order'],s['baseline_order'][:-1],s['baseline_order']*2]:
        with ranking_context(preferences={identity:bad}):actual=plan_explore()
        assert actual==baseline


def test_source_change_uses_current_original_policy():
    with ranking_context() as ctx:plan_explore()
    identity,s=next(iter(ctx.snapshots.items()))
    kwargs=explore_inputs();kwargs['scheduler_load']=.4
    expected=build_explore_worker_branch_plan(**kwargs)
    with ranking_context(preferences={identity:list(reversed(s['baseline_order']))}) as changed:
        actual=build_explore_worker_branch_plan(**kwargs)
    assert actual==expected
    assert not any(e['status']=='preference_consumed' for e in changed.events)


def _baseline_module():
    base=os.environ.get('JEV_BASE_DIR')
    if not base:pytest.skip('original pinned checkout required for independent feature-off differential')
    path=Path(base)/'loopx/capabilities/explore/worker_branch_plan.py'
    module=types.ModuleType('loopx.capabilities.explore._jev_baseline_worker')
    module.__package__='loopx.capabilities.explore'
    exec(compile(path.read_text(),str(path),'exec'),module.__dict__)
    return module


@pytest.mark.parametrize('profile',['generic','adaptive-resilient','moe-router'])
@pytest.mark.parametrize('width',[1,2,3])
def test_feature_off_full_plan_matches_original_source(profile,width):
    baseline=_baseline_module();kwargs=explore_inputs()
    kwargs['harness_profile']=profile;kwargs['worker_width']=width
    expected=baseline.build_explore_worker_branch_plan(**kwargs)
    assert build_explore_worker_branch_plan(**kwargs)==expected
    # Capture is also observational with no altered branch metrics or result shape.
    with ranking_context():assert build_explore_worker_branch_plan(**kwargs)==expected


def test_complete_synthetic_chain_has_real_subprocess_artifacts(tmp_path,capsys):
    import json
    output=tmp_path/'demo'
    assert run_demo(output,live=False,model='fixture-v1')==0
    capsys.readouterr()
    result=json.loads((output/'comparison.json').read_text())
    assert result['provider_kind']=='fixture_injected'
    for scenario in ['todo_order','explore_order']:
        records={r['mode']:r for r in result['records'] if r['scenario']==scenario}
        assert records['off']['selected']==records['shadow']['selected']
        assert records['assist']['selected']!=records['off']['selected']
        assert records['assist']['execution']['fixture_target_evidence'] is True
        assert records['off']['execution']['fixture_target_evidence'] is False
        assert records['assist']['execution']['canonical_completion']=='not_exercised'

@pytest.mark.parametrize('provider',['file','sqlite'])
@pytest.mark.parametrize('mode',['off','shadow','assist'])
def test_actual_explore_cli_preserves_owner_admission(tmp_path,monkeypatch,provider,mode):
    import contextlib,io,json
    from loopx_jev.cli import capture,execute,_original
    from loopx_jev.demo import fixture_response
    from loopx_jev.store import initialize_run
    from canonical_authority_fixture import initialize_canonical_authority,isolate_sqlite_runtime
    from loopx.control_plane.coordination.runtime_shadow import build_runtime_shadow_source_snapshot
    from loopx.control_plane.coordination.local_authority import read_canonical_todos_if_promoted
    from loopx.control_plane.testing.canary_harness import write_fixture_registry
    if provider=='sqlite':isolate_sqlite_runtime(tmp_path,monkeypatch)
    monkeypatch.chdir(tmp_path)
    state=tmp_path/'STATE.md';registry=tmp_path/'registry.json';runtime=tmp_path/'runtime'
    state.write_text('# Goal\n\n## Agent Todo\n\n'
        '- [ ] [P1] Repeat the already-passed plain ASCII test\n'
        '  <!-- loopx:todo todo_id=todo_repeat role=agent status=open task_class=advancement_task claimed_by=agent-a required_write_scopes=artifacts/normal/** -->\n'
        '- [ ] [P1] Probe a combining-mark normalization boundary\n'
        '  <!-- loopx:todo todo_id=todo_probe role=agent status=open task_class=advancement_task claimed_by=agent-a required_write_scopes=artifacts/unicode/** -->\n')
    write_fixture_registry(project=tmp_path,runtime_root=runtime,registry_path=registry,goal_id='goal-demo',domain='software',
                           adapter_kind='generic_project_goal_v0',state_file=str(state),registered_agents=['agent-a'],quota_allowed_slots=None)
    value=json.loads(registry.read_text());value['goals'][0]['spawn_policy']=explore_inputs()['orchestration']
    registry.write_text(json.dumps(value))
    projection,_=build_runtime_shadow_source_snapshot(goal=value['goals'][0],runtime_root=runtime,state_path=state,registry_path=registry)
    initialize_canonical_authority(runtime,'goal-demo',projection,state_path=state,provider=provider);state.unlink()
    args=['--format','json','--registry',str(registry),'--runtime-root',str(runtime),'explore','worker-branch-plan',
          '--goal-id','goal-demo','--agent-id','agent-a','--worker-width','1','--max-todos-per-branch','1','--harness-profile','generic']
    conf=tmp_path/'config.json';conf.write_text(json.dumps({'schema_version':'loopx_jev_branch_config_v0','mode':mode,'model':'fixture-v1','allow_egress':True}))
    basis=tmp_path/'basis.json';basis.write_text(json.dumps({'goal_id':'goal-demo','objective':'Find normalization gaps','acceptance':['Discriminating Unicode evidence']}))
    cap=tmp_path/'cap.json';run=tmp_path/'run';initialize_run(run)
    packets=[]
    def invoke(argv):
        output=io.StringIO()
        with contextlib.redirect_stdout(output):code=_original(argv)
        packets.append(json.loads(output.getvalue()));return code
    before=read_canonical_todos_if_promoted(runtime_root=runtime,goal_id='goal-demo')
    assert capture(args,cap,invoke)==0
    assert json.loads(cap.read_text())['snapshots']
    assert execute(args,config_path=conf,capture_path=cap,basis_path=basis,run_dir=run,report_path=tmp_path/'report.json',
                   invoke=invoke,transport=fixture_response,credential=lambda:'fixture')==0
    actual=packets[-1];selected=actual['selected_worker_branches'][0]
    assert selected['todo_ids']==(['todo_probe'] if mode=='assist' else ['todo_repeat'])
    assert actual['harness_compatibility']['launches_workers'] is False
    assert actual['boundary']['claims_todos'] is False
    assert actual['ab_result']['baseline_selected_branch_ids']==packets[0]['ab_result']['baseline_selected_branch_ids']
    assert read_canonical_todos_if_promoted(runtime_root=runtime,goal_id='goal-demo')==before


def test_projection_clock_is_not_a_decision_revision_but_frontier_is():
    kwargs=explore_inputs();kwargs['projection']={'generated_at':'2026-09-20T00:00:00Z','frontier':[]}
    with ranking_context() as ctx:build_explore_worker_branch_plan(**kwargs)
    identity,snapshot=next(iter(ctx.snapshots.items()));order=list(reversed(snapshot['baseline_order']))
    kwargs['projection']['generated_at']='2026-09-20T00:01:00Z'
    with ranking_context(preferences={identity:order}) as applied:
        actual=build_explore_worker_branch_plan(**kwargs)
    assert actual['selected_worker_branches'][0]['branch_id']==order[0]
    assert any(e['status']=='preference_consumed' for e in applied.events)
    kwargs['projection']['frontier']=[{'node_id':'new','summary':'New material frontier fact'}]
    with ranking_context(preferences={identity:order}) as changed:build_explore_worker_branch_plan(**kwargs)
    assert not any(e['status']=='preference_consumed' for e in changed.events)
