# Jev implementation experiment and branch handoff

[中文](IMPLEMENTATION_REPORT.zh-CN.md)

**Status: experimental archive; no implementation merge into main requested.**
Keep the implementation and this report together for inspection and independent
follow-up. RFC #4749's discussion intake does not approve runtime adoption. This
archive neither changes that decision nor assigns upstream maintenance duties.

## Provenance and upstream handoff

- Original upstream baseline: `04ba65ac1a37c94d964adeedf3ff1f125c5ffe12`.
- Personal integration baseline: `7fef13c73ab68e25878584e0ed61017a4bafa990`.
- Tested implementation: `3b4c1e27f1b2ed2227ee7cb105b57b7f1c69ad52`.
- Archive source: [songoow/loopx:codex/jev-experiment-archive](https://github.com/songoow/loopx/tree/codex/jev-experiment-archive).
- Implementation discussion: [fork PR #1](https://github.com/songoow/loopx/pull/1), targeting a personal integration branch, not upstream main.
- Upstream background: [RFC #4749](https://github.com/loopx-project/loopx/pull/4749).

The publishing account currently lacks upstream write access. The source branch
is not an existing upstream branch. If a maintainer accepts the archive, preserve
its complete history under upstream `codex/jev-experiment-archive`, without
merging or rebasing onto main. Verify the source head and absence of the target
branch first; do not force-push or replace an existing branch:

```bash
git fetch https://github.com/songoow/loopx.git refs/heads/codex/jev-experiment-archive
git show --no-patch --format=fuller FETCH_HEAD
git push https://github.com/loopx-project/loopx.git FETCH_HEAD:refs/heads/codex/jev-experiment-archive
```

Read back both remote branch SHAs and verify equality. This preserves an
experiment; it does not qualify compatibility with current main. Any future
product proposal needs a separate scope and real-task evaluation.

## Delivered implementation

| Area | Implemented | Limit |
|---|---|---|
| D1–D6 | Explicit `loopx-jev assess`, revisioned inputs and host-read evidence | No automatic native Agent or domain-owner takeover |
| D7 | Legal same-cohort preference in scoped-gate fallback | Not a universal Todo selector |
| D8 | Preference after candidate planning, before existing admission | No worker launch; atomic policy requires width=1 |
| Isolation | off/shadow/assist, deadlines, budgets, no retries, stale/cache revocation | Disabling does not undo work or incurred costs |
| Atomic policy | Separate evidence, contribution and adoption decisions | Explicit experiment; pairwise remains default |

[Operation](README.md) covers installation, capture/run, disable and uninstall;
[evidence-policy instructions](EVIDENCE_RANKING.md) cover binding and fallback.
No additional permission, execution, acceptance or settlement authority is
introduced. Existing gates, quotas, resource admission and policy groups remain.

## Outcomes: selection is not delivery

The latest frozen comparison has 24 regression and eight new synthetic cases:
ten semantic families with direction/order variants, not 32 independent real
engineering projects. Source observations are synthetic facts. The following
scores count final owner choices on eight unique-best cases per direction,
including baseline fallback after abstention.

| Arm | D7 | D8 |
|---|---:|---:|
| Original owner | 1/8 | 4/8 |
| Pairwise Jev | 4/8 | 7/8 |
| Evidence-atomic Jev | 1/8 | 4/8 |
| Bounded Codex, same evidence and atomic reducer | 8/8 | 8/8 |

Pairwise made 32 live calls. Atomic made 28 calls plus four pre-network structural
rejections; it produced 26 abstentions and two `invalid_response_or_local_io`
failures, with no usable recommendation. Its correct choices came from baseline.
The combined error category cannot distinguish protocol from local I/O failures.
Codex made 28 bounded judgments plus the same four structural rejections; its
one-hot label adaptation is not model confidence. Negative results were retained
without deleting cases, lowering the threshold or retrying.

Combined predeclared choice/tie/abstention/structural-rejection agreement was
27/32, 19/32 and 32/32 respectively. That mixes structural checks with judgments
and is not production accuracy. This round did not execute selected coding work.

Earlier native Codex comparisons completed 6/6 in both D1–D6 off/assist arms and
4/4 in both D7/D8 arms, with independent acceptance and broken-copy checks.
Unassisted Agents could correct poor initial selections. No extra completed task
or consistent speed improvement was established. See [historical validation](VALIDATION.md).

## Timing and verification

| Latest actual calls | Count | Median ms | P95 ms |
|---|---:|---:|---:|
| Pairwise Jev | 32 | 778.695 | 1169.586 |
| Evidence-atomic Jev | 28 | 969.471 | 1104.821 |
| Bounded Codex | 28 | 9701.111 | 13032.679 |

Jev includes evidence read, assessment wrapping, network/subprocess, storage and
owner consumption. Codex measures process start to exit, excluding owner
consumption. Different harnesses do not establish pure inference speed ratios.
P95 uses nearest-rank. Nanosecond counters do not imply nanosecond precision;
small single-run samples are not an SLA. Currency costs are unknown. Jev pins
`jev-1.13.0`; Codex requests `gpt-6-astra` / medium without exposing a pinned
resolved model revision.

Evidence-read/assessment/owner median phases are 1.791/751.260/23.844 ms for
pairwise and 1.387/942.790/23.047 ms for atomic. Independently computed medians
must not be added as a substitute for the total median.

Local focused Python: 250 passed; TypeScript: 32 passed; final new-policy rerun:
27 passed. Coverage includes actual CLI/File/SQLite, feature-off differentials,
protocol errors, stale evidence and replay revocation. Changed product files and
new tests pass Ruff; the new module passes strict mypy. Whole optional-package
strict mypy still has 75 errors versus 80 on the same-command baseline. Neither
whole-package static checks nor all repository CI are claimed green.

Live experiments run locally, independently of CI; CI only runs deterministic
credential-free tests. Raw trajectories, private inputs, credentials and local
artifacts are excluded. Published aggregates are study records, not independent
reproduction. Public demos/tests reproduce integration behavior, not the complete
private experiment execution.

## Disposition

Close this stage as a branch archive, with no main implementation merge request
and no assumed upstream maintenance obligation. Do not promote the atomic gate.
Any follow-up should freeze real observed facts, diagnose adequacy judgments,
and compare final acceptance, costs and timings of the complete Agent workflow.
Claude, long-horizon recovery, universal Todo selection, PostgreSQL qualification,
multi-worker optimization and live packed/separate question equivalence remain
unqualified.
