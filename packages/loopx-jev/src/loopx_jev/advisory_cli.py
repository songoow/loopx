"""Explicit artifact-based advisory invocation, outside all owner transactions."""
from __future__ import annotations

import json
from pathlib import Path
import time

from .advisory import validate_input
from .config import load_config, read_json


def assess(input_path: Path, basis_path: Path, config_path: Path | None,
           run_dir: Path, report_path: Path, *, transport=None, credential=None) -> int:
    started = time.perf_counter_ns()
    config = load_config(config_path)
    if config.mode == 'off':
        print(json.dumps({'status': 'disabled', 'advice': None}))
        return 0
    from .runner import assess_one, read_basis
    from .store import RunStore, atomic_json
    if report_path.exists() or not report_path.parent.is_dir():
        raise ValueError('use a new report in an existing directory')
    snapshot, digest = read_json(input_path, 65536)
    validate_input(snapshot, config.max_candidates)
    basis, evidence_current = read_basis(basis_path, Path.cwd())
    if not isinstance(basis.get('goal_id'), str) or not basis['goal_id'].strip():
        raise ValueError('explicit_goal_identity_required')
    def current():
        try:
            observed = load_config(config_path)
            return (observed.generation == config.generation and observed.mode != 'off'
                    and read_json(input_path, 65536)[1] == digest and evidence_current())
        except (OSError, ValueError, TypeError):
            return False
    prepared = time.perf_counter_ns()
    kwargs = {}
    if transport is not None: kwargs['transport'] = transport
    if credential is not None: kwargs['credential'] = credential
    result = assess_one(snapshot, basis, config, RunStore(run_dir), current, **kwargs)
    evaluated = time.perf_counter_ns()
    fresh = current()
    advice = result.get('assessment') if config.mode == 'assist' and fresh and result['status'] == 'completed' else None
    report = {'format': 'jev_advisory_report_v0', 'mode': config.mode,
              'source': snapshot['source'], 'input_sha256': digest,
              'assessment_record': result, 'advice': advice, 'fresh_at_readback': fresh,
              'boundary': 'Explicit caller-exported evidence only; no source discovery, permission, verification, installation or plan-commit authority.',
              'timing_ns': {'prepare': prepared - started, 'assessment_inclusive': evaluated - prepared,
                            'readback_guard': time.perf_counter_ns() - evaluated}}
    # Persist a measured pre-write report, then expose write/total timing only in
    # the returned receipt; no self-referential claim to time its own final write.
    write_started = time.perf_counter_ns()
    atomic_json(report_path, report)
    finished = time.perf_counter_ns()
    receipt = {'report_written': True, 'status': result['status'], 'advice': advice,
               'timing_ns': {**report['timing_ns'], 'report_write': finished - write_started,
                             'command_total_before_stdout': finished - started}}
    print(json.dumps(receipt, ensure_ascii=False))
    return 3 if result['status'] in {'failed', 'stale'} else 0
