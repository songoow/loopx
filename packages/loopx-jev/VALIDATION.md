# Validation and claim boundaries

The pilot remains based on upstream `04ba65ac1a37c94d964adeedf3ff1f125c5ffe12`
and the personal integrated branch. This is not upstream adoption or permission
to mutate active Goals. [中文](VALIDATION.zh-CN.md)

## Implemented and exercised

D1–D6 have an explicit `loopx-jev assess` entrypoint over caller-declared,
revisioned inputs and host-read local evidence. This is a usable bounded advisory
caller, not automatic integration into every upstream owner. D7/D8 retain the
actual scoped fallback selector and Explore planner capture/run entrypoints.
Default off avoids optional input, ledger, credential and transport access.

All directions preserve existing permissions, ownership, acceptance and
settlement. D1 separates goal relation from evidence increment; missing history
forces unknown increment. D3 refuses to infer support without evidence refs.
D4 retains every candidate and required source. D5 suggests discovered skills
without installation; D6 compares supplied alternatives without committing plans.

Focused validation covers configuration, strict JSON, duplicate response fields,
partial coverage/abstention, malformed membership, missing evidence, exact-head
claims, stale input, revoked cached advice, transport failures, durable attempt
budgets, source readback, example schemas and feature-off isolation. Deadlines
include parent preparation and worker spawn; malformed responses cannot become
preferences. Timing records distinguish sequential phases from inclusive totals.

The continuation was tested with Python 3.11.7, Node 22.23.2 and pytest 9.1.1.
Original qualification also used Python 3.13.5; CI uses Python 3.13. Exact-head
CI, rather than these version notes, determines whether a later revision passed.
File/SQLite tests include actual CLI calls and canonical completion; a separate
pinned source supplies nine complete feature-off planner differentials. Existing
quota, decision-scope, Explore and TypeScript settlement regressions remain.

Node 25.2.1's SQLite was rejected during initial local qualification. Merely
changing PATH reused an old Effect service. A fresh TMPDIR and qualified Node
passed without restarting unrelated services or weakening qualification.

## Bounded live comparisons

The expanded study used 21 predeclared synthetic cases with two independent
calls per case per model: 42 Jev calls and 42 Codex bounded no-tool judgments.
Task evidence and finite question meanings matched; API wrappers, system context,
output formats and harness overhead did not. Repeated calls are not independent
tasks, and constructed-case agreement is not production accuracy.

| Direction | Calls per model | Jev effective exact-label agreement | Codex agreement |
| --- | ---: | ---: | ---: |
| D1 progress | 12 | 9/12 | 12/12 |
| D2 owner reuse | 6 | 4/6 | 6/6 |
| D3 claims | 6 | 6/6 | 4/6 |
| D4 material | 6 | 6/6 | 6/6 |
| D5 skills | 6 | 6/6 | 6/6 |
| D6 replanning | 6 | 6/6 | 6/6 |

Jev's effective agreement was 37/42; raw highest-probability labels agreed on
38/42. The original 0.6 threshold was not lowered to improve results. Both drift
trials abstained; one changed-goal trial left increment unknown. Two owner cases
classified a display cache as related-but-distinct instead of unrelated, without
recommending unsafe reuse. Codex classified two overbroad claims as insufficient
rather than contradicted; neither classification endorsed those claims. Unknown
answers can be correct, and these disagreements do not all represent consequential
errors. Determinate coverage was 61/76 items for Jev and 64/76 for Codex.

Pinned `jev-1.13.0` was verified in every successful provider response. Codex used
requested `gpt-6-astra` with medium reasoning; its fixed resolved model version
was not exposed by the CLI. Currency cost remains unknown.

## Native working-agent outcomes

Six independent synthetic work projects were each run off/assist from identical
initial files. All 12 native Codex sessions produced artifacts that passed
independent contract checks. All 12 validators rejected deliberately broken
artifacts in disposable copies. Helper/experiment execution and preservation of
read-only evidence were separately checked. Both arms completed 6/6 cases:
**no incremental successful outcome was observed**. Some assisted sessions were
faster and others slower; one formal run per arm cannot establish efficiency.

Assist consumed a real assessment of that exact initial workspace, with the
working Agent free to investigate and reject advice. It was an explicit study
handoff, not an installed native Goal hook or continuous refreshed controller.
The initial exploratory work batch had visible host logs and underspecified
output types; it is excluded from formal outcome/timing totals. Fresh formal
sessions isolated logs and repositories, froze the clarified contracts, and
reassessed the two changed goal bases rather than reusing stale advice.

Four additional D7/D8 live cases used the actual selector/planner. Preferences
selected the useful alternative under the original objective, and preserved the
baseline when the changed objective made it preferable. All four matched the
predeclared choices; this does not establish whole-system scheduling benefit.

Expanded-study provider calls total 54: 42 bounded comparisons, four ranking
cases, six initial work assessments and two reassessments after contract
clarification. No automatic retries or cached replies were counted as fresh
trials. Earlier D7/D8 qualification calls remain separate historical evidence.
Claude is excluded from the current scope.

## Timing and reproduction

Observed complete bounded-client medians/P95 were 1952.985/3531.167 ms for Jev
and 10324.081/17424.028 ms for Codex. P95 uses nearest-rank. Jev request-to-headers
median was 1205.551 ms; this includes DNS/TLS, network, queueing and execution,
**not server-only inference time**. System/harness input-token overhead differs
substantially; these numbers cannot establish pure model speed or cost advantage.

[Examples and timing contract](examples/advisory/README.md) document nanosecond
clock representation, nested phases, replay attribution, report-write timing,
explicit activation and disable behavior. Host work and independent validation
are separate measurements. Human material-assembly time remains unmeasured.
Public examples and durable tests ship here; raw study drivers, trajectories and
per-call records remain outside the tracked product and CI surface.

From an installed checkout environment, with a fresh temporary runtime directory
and the qualified Node on PATH:

```bash
export JEV_BASE_DIR=/path/to/a/separate/pinned/baseline-checkout
python -m pytest packages/loopx-jev/tests -q
node --no-warnings --experimental-sqlite --experimental-strip-types --test \
  tests/control_plane_ts/scoped_gate_fallback.test.ts \
  tests/control_plane_ts/decision_scope.test.ts \
  tests/control_plane_ts/turn_settlement.test.ts
```

Missing baseline causes explicit differential skips, not passing parity. No
statistically supported quality/cost gain, PostgreSQL qualification, full-suite
certification, long-horizon recovery or automatic upstream adoption is claimed.
