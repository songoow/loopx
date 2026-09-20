# Validation and claim boundaries

Baseline: upstream `04ba65ac1a37c94d964adeedf3ff1f125c5ffe12`.
The source was read as a complete tracked archive; local work uses an isolated
worktree. No active user Goal, lease, credential store or worktree was modified.

## Executed locally

Python 3.13.5, Node 22.23.2, pytest 9.1.1. The following groups run in separate
processes; tests themselves include bounded concurrent threads/processes.

- Adapter: strict config/JSON, whole-request deadline, key isolation, no retries,
  candidate coverage/cohorts, consistent ties, cycles, abstention, changed evidence,
  budget sharing and expired-detail tombstones.
- D7: the real original TypeScript selector, the full quota CLI on Markdown,
  File and SQLite, disabled/shadow/assist behavior, current-source changes,
  concurrent config disable, optional transport failures, and actual independent
  validator execution before canonical Todo completion on File/SQLite.
- D8: the real builder and full Explore CLI on File/SQLite, fixed profiles,
  unchanged candidate metrics, strict membership, disabled behavior, preservation
  of resource/admission boundaries and original dry-run baseline identity.
- Feature-off differential: complete planner result equality against a separate
  pinned original source across generic/adaptive-resilient/moe-router profiles.
- Existing regressions: scoped fallback CLI, decision-scope runtime/consistency,
  Explore router/resources/monitors/affinity, and TypeScript settlement.

The capture/consume integration found and fixed one concrete issue during
implementation: read-model `projection.generated_at` changes on refresh and is
not a decision fact. Only that display timestamp is excluded. A regression test
separately proves real frontier changes invalidate the hint.

## Run

From the branch root with its development environment:

```bash
export PYTHONPATH="$PWD/packages/loopx-jev/src:$PWD:$PWD/tests:$PWD/tests/control_plane"
export JEV_BASE_DIR=/path/to/a/separate/pinned/baseline-checkout
python -m pytest packages/loopx-jev/tests -q
node --no-warnings --experimental-sqlite --experimental-strip-types --test \
  tests/control_plane_ts/scoped_gate_fallback.test.ts \
  tests/control_plane_ts/decision_scope.test.ts \
  tests/control_plane_ts/turn_settlement.test.ts
```

The nine independent-source differential cases explicitly skip if the separate
baseline is absent. CI checks out that baseline independently; a skip is not a
passing differential. Current counts/status belong in the exact-head CI output,
not an evergreen claim that later revisions passed.

## Not established

No live Jev response/quality measurement, actual Codex/Claude coding session,
long-horizon native Goal, PostgreSQL qualification, general model improvement,
full-suite certification or automatic upstream adoption is claimed. A provided
API key was not committed or installed as a repository secret. The local network
could not resolve the TypeSafe host, so fixture replies are never labeled live.

The synthetic subprocess is not a coding model. The real canonical-completion
checks are not a claim of exercising every Turn settlement phase. D8 remains a
read-only plan; protected worker execution still follows its existing owner.

A meaningful live comparison uses independent initial state for off and assist,
the same branch/code/model/budget, unchanged evaluators, and records actual
selection plus later outcomes. Include unchanged selections, bad preferences,
necessary prerequisites, misleading descriptions, ties and failures. A model's
probability is not an outcome score. Report unknown cost as unknown.
