# Explicit D1–D6 examples

These synthetic caller packets exercise the optional `loopx-jev assess` command.
They do not claim that an upstream owner exported or approved their contents.
Each directory contains a revisioned input, an operator goal basis and a local
file that the adapter actually reads. Run from the chosen example directory so
relative evidence references resolve correctly.

| Example | Finite result | Authority retained elsewhere |
| --- | --- | --- |
| D1-progress | Goal relation and evidence increment, separately | Goal acceptance, progress and settlement |
| D2-reuse | Reuse / related but distinct / unrelated / unknown | Semantic registration and owner selection |
| D3-claims | Support / contradiction / insufficient evidence per claim | Exact-head review and merge |
| D4-material | Complete suggested order and mandatory source IDs | Required reads, source truth and retrieval coverage |
| D5-skills | Applicable discovered candidate IDs | Installation, activation and tool permissions |
| D6-replan | Alternatives adding evidence versus repeating it | Legal-plan creation, selection and commitment |

With the optional package installed, this is a no-network check:

```bash
cd packages/loopx-jev/examples/advisory/D1-progress
loopx-jev assess --input input.json --basis basis.json \
  --config ../config.off.json --run-dir unused --report unused.json
```

For an authorized live study, copy `config.off.json` outside tracked files, set
`mode` to `assist` (or `shadow`) and `allow_egress` to `true`. Keep a pinned model,
explicit scenarios and finite limits. Configure `TYPESAFE_API_KEY` in the process
environment. Initialize a **new** ignored run directory, then invoke:

```bash
loopx-jev init-run /your/private/new-run --max-requests 6
loopx-jev assess --input input.json --basis basis.json \
  --config /your/private/jev-config.json --run-dir /your/private/new-run \
  --report /your/private/new-report.json
```

Use absolute private paths when running from an example directory. Existing
reports are not overwritten. A shared run directory serializes reservations and
replays identical inputs rather than charging again. Independent repeated trials
need separate explicitly budgeted runs. `shadow` records judgments but exposes
no consumable `advice`; `assist` returns advice only after freshness readback.
`off` does not read inputs, evidence, ledger or credentials and writes no report.
Delete the private configuration or choose `off` to disable; uninstalling the
optional package leaves original LoopX callers available.

Missing history forces D1 increment to unknown. Missing observed evidence stops
D1 evaluation. Claims without attributable references remain insufficient even
if the model says supported. A low-probability answer becomes unknown per item,
so partial coverage is visible rather than suppressing all other known items.
None of these guards turns supplied evidence or a model verdict into truth.

Source revision is a caller declaration bound to the exact input-file hash,
not proof of canonical owner adoption. The CLI does not discover the complete
repository, run upstream reviews, fetch remote evidence or install hooks. Supply
current exported facts and actual artifact references; missing context may make
an otherwise sound model judgment wrong. D7/D8 retain their existing capture/run
entrypoints and typed owner checks.

## Timing interpretation

Durations are sampled with `perf_counter_ns` and reported as integer nanoseconds.
This describes the clock representation, not nanosecond physical accuracy.
Scheduling, network and machine load remain part of observed wall time.

- `assessment_timing_ns`: sequential eligibility, preparation, reservation,
  pre-dispatch guard, transport, response validation, completion and persistence.
  The attempt file ends before timing its own write; the returned record also
  includes the measured write and `assessment_total_ns`.
- `transport_timing_ns`: request preparation, process spawn, wait, decode and
  inclusive total. The wait includes the child and IPC; do not add nested child
  durations to this total. The request deadline includes parent preparation and
  spawn, rather than granting another full deadline after startup.
- `worker_timing_ns`: preparation, request-to-headers, body read and framing.
  Request-to-headers includes DNS, connection/TLS, network, provider queueing and
  inference. **Server-only inference time is not exposed and remains unknown.**
- The CLI receipt separately times report writing; the report itself records
  pre-write phases. D7/D8 capture/run reports time preparation, assessment and
  owner invocation separately. Their owner invocation does not time later work.
- Cached results have `replayed` and `cached_provider_measurements`; retained
  provider timings/usage refer to the original call, while replay timing is new.
- Host execution and independent validation must be timed by the experiment
  driver. CLI first-event or completed-message latency is not time to first token.
  A single run, different prompts/tools, or different system-token overhead does
  not establish a model speed or quality advantage.

The expanded study uses fixed labels, repeated independent calls and keeps
abstention distinct from error. Its small constructed cases are diagnostic,
not production-distribution accuracy or statistically proven outcome benefit.
