# Experimental evidence-bound selection

[中文](EVIDENCE_RANKING.zh-CN.md)

This optional policy separates evidence adequacy, incremental contribution, and
preference adoption. It is an experiment, not a recommended replacement for the
existing pairwise policy. Local synthetic live comparisons found excessive
abstention with Jev; correct abstention alone does not establish useful selection.

## Enable and operate

Follow the existing [capture/run instructions](README.md). Add
`"ranking_policy": "evidence_atomic"` to the explicit local configuration, with
`mode: shadow` initially, a pinned model, and `allow_egress: true`. Credentials
remain in `TYPESAFE_API_KEY`. No automatic host hooks are installed.

After capture, add `ranking_evidence` to the existing basis manifest:

```json
{
  "goal_id": "example-goal",
  "objective": "Obtain a new independent compatibility result",
  "acceptance": ["The independent compatibility check passes"],
  "evidence": [{"ref": "observations.txt"}],
  "ranking_evidence": [{
    "snapshot_id": "COPY_THE_EXACT_KEY_FROM_CAPTURE_SNAPSHOTS",
    "candidates": {
      "COPY_FIRST_ACTUAL_CANDIDATE_ID": ["observations.txt"],
      "COPY_SECOND_ACTUAL_CANDIDATE_ID": ["observations.txt"]
    }
  }]
}
```

Use actual keys from `capture.snapshots` and each snapshot's `baseline_order`,
covering every candidate exactly. References resolve against the run workspace,
not the basis file's directory. Supply observations relevant to each candidate;
sharing a file is allowed when it contains those observations. The reader obtains
text and hashes from files; do not supply claimed `text`, `sha256`, or `origin` in
the manifest. A readable file and matching digest prove neither truth nor
semantic completeness. Evidence remains untrusted input, not execution authority.

Run the same `loopx-jev run` command with the same captured original command.
Read `assessments[].ranking_decision.reason` and `.signals` in its report alongside
status, `preference_consumed`, and the owner's final choice. Structural rejection
happens before key lookup or network dispatch. To consume a recommendation,
explicitly switch to `mode: assist` and recapture if the source changed.

## Contract and fallback

Only D7 scoped fallback and D8 single-worker planning (`width=1`) are supported,
within one original policy-equivalent cohort. Other scopes retain the owner's
choice without a provider call. D1–D6 are unaffected.

Each candidate gets independent evidence and contribution questions, in addition
to the existing pairwise questions. Four candidates require fourteen questions,
not six. All responses must pass the existing strict protocol checks. Every
candidate's evidence must be sufficient, and its contribution must be known at
the configured probability threshold. A unique candidate must then beat every
alternative directly and have evidenced positive contribution. Uncertainty among
losing pairs need not veto that candidate; losing candidates retain baseline
order. Confident all-pair ties preserve the baseline. There is no numeric utility
conversion, permission grant, worker launch, or completion authority.

`ranking_decision` explains evidence/contribution uncertainty, absence of a
dominant candidate, lack of increment, equivalence, or recommendation. Failures,
missing evidence, and uncertainty retain the original owner behavior. Source,
configuration, and evidence freshness are checked again before consumption and
cache replay. Snapshot binding is not an atomic transaction across stores.

For rollback set `ranking_policy: pairwise` to restore the previous experimental
policy, or `mode: off` / invoke the original LoopX command to disable Jev. A
policy change has a different request identity. Switching off does not undo
already executed work, sent data, or costs. Existing request and byte budgets,
no-retry transport, and uninstall instructions still apply.

## Validate locally

With the checkout/test environment installed and qualified Node version selected:

```bash
.venv-jev/bin/python -m pytest -q packages/loopx-jev/tests/test_atomic_ranking.py \
  packages/loopx-jev/tests/test_d7.py packages/loopx-jev/tests/test_d8.py
```

These deterministic tests cover real selector/planner/CLI and File/SQLite paths,
off/shadow parity, stale evidence, separate cache identities, malformed replies,
and fallback. Injected answers prove integration, not model quality. Live
comparisons are separate local experiments and are not required by CI. Use a
fresh isolated temporary runtime when qualifying SQLite.

## Implementation references

This implementation independently adapts bounded decisions and freshness from
[browser-use/jev-ultrafast](https://github.com/browser-use/jev-ultrafast/tree/1231850a0bf1a0c0341fe408ef1668dbbfdfac46),
atomic questions from
[fast-jev-compaction](https://github.com/tamaratran/fast-jev-compaction/tree/e3f262a7f4d42bd8dd32ced30d26176f7cb545b0),
and separate adoption/fallback policy from
[jev-router](https://github.com/gargpratyush/jev-router/tree/38da6b84ea01241bfc41fbddc0928d0f40a703f0).
[kev](https://github.com/jaredpalmer/kev/tree/5f78968927069eaacc3b2bdb688586989b3933ac)
informs protocol conformance testing; packed-versus-separate live probability
equivalence has not been established here. No third-party source was copied.
