# Jev selection pilot (personal branch only)

An optional, zero-SDK wrapper for **two specific existing LoopX decision paths**.
This is an experimental implementation of D7/D8, not upstream adoption of the
Jev RFC. It adds no manager, native Goal loop, worker launcher or authority.

[中文说明](README.zh-CN.md) · [Test/evidence boundaries](VALIDATION.md)

## What is connected

| Path | Actual consumer | Scope |
|---|---|---|
| D7 | `todo.decision_scope.evaluate` / scoped gate fallback | Only the original owner's eligible, same-priority, conservatively policy-equivalent cohort; not every Todo selector |
| D8 | `build_explore_worker_branch_plan` | Original bundles/profile/router, then preference, then the unchanged scheduler/resource/dependency admission |

`off` calls the original command without loading the optional transport, reading
its key, building a Jev snapshot or writing Jev records. `shadow` runs the original
command first and evaluates an earlier captured snapshot afterwards; it does not
show advice to the working Agent. The explicit wrapper still waits to return its
report, so shadow is **not** a zero-overhead/L1-observer claim. `assist` evaluates
first and consumes a complete preference only when the current owner snapshot,
local source versions, config and evidence still match.

Original holds/refusals remain. Model failure cannot make blocked work eligible.
Changing config to `off` prevents future consumption, including a late answer;
it cannot undo bytes already sent, incurred fees, or previously accepted work.
The prototype does not make this check atomic with arbitrary external effects.
Actual execution must still recheck its original admission and identity.

## Install from this branch

Requires Python 3.11+ and the branch's supported Node (22.18+ for File authority;
use Node 22.23.2, as in CI, for the qualified SQLite runtime). Use an isolated
environment from the **repository root**, not a globally installed LoopX:

```bash
uv venv .venv-jev
uv pip install --python .venv-jev/bin/python -e '.[test]' -e packages/loopx-jev
.venv-jev/bin/loopx-jev --help
```

The package deliberately has no SDK or model dependency. The core still has
`dependencies = []`. Do not mix its active capture interfaces with an older core.
Do not run `uv sync` on this environment without including the optional package;
it may remove an independently installed extra.

## Run the self-contained example (no key, no network)

```bash
.venv-jev/bin/loopx-jev demo --output-dir .local/jev/demo-001
```

Use a new directory for each demonstration. This invokes the **actual original
TS selector and Explore planner**, injects a clearly labeled fixture response,
runs a synthetic subprocess and independently reads its artifact. Expected
plumbing: off/shadow choose the baseline; assist can select the legacy fixture
or discriminating Unicode probe. The CLI/File/SQLite/canonical-completion
integration is additionally exercised by `tests/test_d7.py` and `test_d8.py`.

This demo is not a live Codex/Claude run, full Turn settlement, or evidence that
Jev makes better choices. The independent completion tests exercise the real
canonical writer and pinned acceptance commands, but use a fixture coding host.

## Explicit live Jev check

Only the synthetic demo data is sent. Rotate any key that was pasted into chat.
Read a new key interactively rather than putting it in shell history or a file:

```bash
printf 'TypeSafe API key: '
read -r -s TYPESAFE_API_KEY
printf '\n'
export TYPESAFE_API_KEY
.venv-jev/bin/loopx-jev demo --live --model jev-1.13.0 \
  --output-dir .local/jev/live-001
unset TYPESAFE_API_KEY
```

Confirm the explicit model is available to your account; there is no silent alias
or provider switch. At most two calls are reserved for this demo. The endpoint is
fixed to TypeSafe HTTPS; keys go through a private child-process pipe, not argv.
The transport has one whole-process deadline, disables redirects/proxies, kills
and reaps a timed-out worker, and never retries or logs response error bodies.

A requested live demo exits nonzero if it cannot obtain valid model responses.
Read `assessments` in `comparison.json`: a valid abstention/inconsistent preference
is different from unavailable transport. Missing usage/cost stays unknown.
A successful HTTP call is not proof of selection quality. The development
environment could not resolve TypeSafe, so no real-model quality is asserted.

## Use a real existing project command

This first pilot uses **explicit capture and replay**, so ordinary status polling
cannot cause inference. Both commands use the same cwd, source files and exact
LoopX argv. Supply `--registry`, `--runtime-root` and `--goal-id` explicitly.
No active project is created, promoted or altered just to enable Jev.

```bash
mkdir -p .local/jev
.venv-jev/bin/loopx-jev init-run .local/jev/run-001 --max-requests 20

.venv-jev/bin/loopx-jev capture --output .local/jev/capture-001.json -- \
  --format json --registry /your/private/registry.json \
  --runtime-root /your/private/runtime quota should-run \
  --goal-id your-goal --agent-id your-agent

.venv-jev/bin/loopx-jev run --config .local/jev/config.json \
  --capture .local/jev/capture-001.json --basis .local/jev/basis.json \
  --run-dir .local/jev/run-001 --report .local/jev/report-001.json -- \
  --format json --registry /your/private/registry.json \
  --runtime-root /your/private/runtime quota should-run \
  --goal-id your-goal --agent-id your-agent
```

For D8, replace the final existing command in **both** invocations with:

```text
explore worker-branch-plan --goal-id your-goal --agent-id your-agent
  --harness-profile generic --worker-width 1 --max-todos-per-branch 1
```

Use your already authorized profile; the wrapper never enables Explore or widens
spawn policy. Capture executes the real original command, including its already
configured turn-start effects; capture is not a generic "everything is read-only"
promise. A source changed during capture makes that capture ineligible; recapture
rather than ignoring the conflict.

### Configuration

Copy [examples/config.off.json](examples/config.off.json) to the ignored local
configuration location. Only the following schema is accepted:

```json
{
  "schema_version": "loopx_jev_branch_config_v0",
  "mode": "off",
  "scenarios": ["todo_order", "explore_order"],
  "model": "jev-1.13.0",
  "allow_egress": false,
  "minimum_preference_probability": 0.6,
  "limits": {
    "max_candidates": 6,
    "deadline_ms": 5000,
    "max_requests_per_run": 20,
    "max_parallel": 2,
    "max_request_bytes": 65536,
    "max_response_bytes": 65536
  }
}
```

Set `mode` to `shadow` or `assist` and explicitly authorize data egress before
setting `allow_egress=true`. A present key does not enable anything. The threshold
and limits are experimental engineering settings, **not calibrated safety or
quality claims**. Credentials use only `TYPESAFE_API_KEY`; the proposed historical
`credential_env` and `enabled` fields are deliberately not supported.

The run manifest is explicitly initialized once. Concurrent calls share a finite
reservation budget and same-request deduplication; deleting a result detail leaves
its reservation/tombstone and does not authorize another send. A lost/ambiguous
attempt is not automatically retried. Deleting the entire run requires explicit
new initialization and starts a new authorized run, not an exactly-once guarantee
across deletion or independent run directories. No remote idempotency is claimed.

### Goal basis and evidence

The local JSON manifest contains `goal_id`, `objective`, nonempty `acceptance`,
optional `non_goals`, `horizon`, `already_known`, and at most eight `evidence`
items (`ref` relative to cwd; optional description). Use an explicit owner-defined
criterion, not an automatically invented goal. See [examples/basis.json](examples/basis.json).

The adapter reads exact file bytes and binds their hashes, the basis file, the
registry and current canonical provider revision (or the legacy state file).
It checks these at capture and consumption; this is **not** a cross-store atomic
snapshot. It neither promotes a provider nor reads Markdown after canonical failure.
The explicit study basis is not a substitute for current runtime acceptance.
Data is bounded; oversized candidate sets are skipped, not silently top-k filtered.
Only read-model `projection.generated_at` is excluded from D8 decision identity;
actual frontier facts, tasks, profile/router, resources and source revisions remain.

Local capture/report files contain private paths and task material and are
written with private file permissions. Never commit them. The credential-pattern
check is a best-effort guard, not general DLP or an upload authorization. Review
exact input and provider data policies before allowing real project egress.

## Readback, stopping and uninstall

Reports distinguish suggested order, whether an exact current snapshot consumed
it, and the owner's final selected items. A downstream native Agent can make a
different legal choice. The wrapper **does not install a Codex/Claude hook**, start
workers, force a native Goal, or claim every selection path is integrated.
[The optional usage note](SKILL.md) can guide an existing host without adding a
second driver. Full native-host integration remains unqualified.

Set `mode=off`, or invoke the original `loopx` command directly. Off does not need
a basis/capture/run directory or a Jev key and creates no assessment report.
Uninstall with `uv pip uninstall --python .venv-jev/bin/python loopx-jev-pilot`.
The core keeps its original default behavior without the optional package.
Preserve existing run tombstones while reusing run identities; archive or remove
private artifacts only as an explicit operator action. No business state is rolled
back by disabling or uninstalling.

## Compare with a real working agent

Run off/assist in separate directories with identical initial files, model and
work budget. Record the actual selector/planner choice, then give the working
agent the same legal task set and that recommendation. Allow it to choose a
different legal task; forced compliance measures ordering alone. Independently
validate generated artifacts and record overrides, usage, elapsed time, failures
and unchanged outcomes.

In the initial bounded examples, live Jev changed D7/D8 ordering, but Codex also
chose the useful work with Jev off. Both arms passed artifact readback. This is
not evidence of a quality gain; single-run timing differences cannot establish an
efficiency gain either. CLI login status is not proof that model calls work;
authentication failures remain incomplete host comparisons.

For SQLite retesting, create a fresh temporary directory and set TMPDIR for that
test process. Changing PATH alone can reconnect to an Effect service started
with the old Node. Do not restart a runtime serving unrelated Goals for a study.
