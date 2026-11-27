# First capture run, 27 November 2026

The twin ran in the build sandbox from 14:06 to 14:39 UTC: the OpenTelemetry Demo at release 3.1.0, 23 containers, the load generator's HTTP users only, the capture add-on and the sandbox override from [`../run/`](../run/).

Two flags were flipped by rewriting `src/flagd/demo.flagd.json`, which flagd watches. Each flip was logged as a change event:

| Time (UTC) | Change | Why |
| --- | --- | --- |
| 14:22:19 | `emitRawPii` off → on | Change C7: lineage that exists only under a flag (decision D30) |
| 14:24:10 | `emitRawPii` on → off | |
| 14:24:55 | `paymentFailure` off → 50% | Incident I1 |
| 14:30:09 | `paymentFailure` 50% → off | End of I1 |

## Files

| File | What it is | Made by |
| --- | --- | --- |
| `change-events.jsonl` | The four flag changes, one JSON object per line: time, flag, its URN, from, to | The flip script used in the run |
| `observed-edges.json` | Every edge the capture produced, with counts; the score against the golden graph; columns per database edge; the name coverage of the alias table | `python3 code/observed_edges.py <capture> fixtures/otel-demo-3.1.0/golden-graph.json --aliases fixtures/otel-demo-3.1.0/aliases.json --json …` |
| `checks-run.json` | Every check at every one-minute step, first failures, recovery, and the root-cause narrowing at the first failure | `python3 code/run_checks.py <capture> fixtures/otel-demo-3.1.0 --events change-events.jsonl --json …` |

The raw capture (96 MB of OTLP JSON: traces, logs and metrics) is not kept here. It holds only the demo's synthetic data, but it is large and any rerun reproduces it. Rerun the twin with the commands in [doc 07](../../../docs/07-reference-slice-otel-demo.md#running-it) to get a fresh one.

## Second run: the incident corpus, 16:54 to 18:43 UTC

The same twin, restarted with 15 simulated shoppers instead of 5 so that a two-minute window holds enough orders to judge a rate. Two checks were added before the run, with thresholds fixed in advance: checkout latency and accounting consumer lag. After a 12-minute baseline, a script injected nine incidents, each on for 4 minutes and then 5 or more minutes of recovery. Every change was logged as a change event (`change-events-run2.jsonl`).

| Incident | Injection | Family |
| --- | --- | --- |
| I5 | `cartFailure` 50% | silent failure |
| I7 | accounting service stopped | consumer outage |
| I2 | `kafkaQueueProblems` on | consumer lag |
| I3 | `productCatalogLockContention` on | storage contention |
| I4 | `paymentUnreachable` on | unreachable address |
| I8 | `intlShippingSlowdown` 10sec | latency only |
| I9 | `recommendationCacheFailure` on, then `paymentFailure` 25% a minute later | decoy outside the lineage |
| I10 | `loadGeneratorFloodHomepage` on | volume surge |
| I6 | `productCatalogFailure` on, through its targeting rule | dependency failure |

The first attempt at I6, at 17:15, changed the flag's default variant. Its targeting rule overrides the default, so nothing was injected. The attempt is kept in the log, relabelled as void, because its change events are real decoys on the timeline. I6 was rerun through the rule at 18:33. Afterwards the thin dbt model was built in the twin under its own login, and the twin was stopped.

| File | What it is |
| --- | --- |
| `change-events-run2.jsonl` | Every change and run marker of the second run |
| `observed-edges-run2.json` | The second capture scored against the golden graph: precision 1.00, recall 0.90, 13 of 13 asserted edges, 55 of 55 names resolved |
| `incident-replay.json` | Both runs' incidents scored with `python3 code/run_checks.py <capture> fixtures/otel-demo-3.1.0 --events <change events> --replay`: checks fired, minutes to detect, narrowing, and the ranked causes with every score term |

The second capture was 650 MB and is not kept.

## What it showed

See [doc 09](../../../docs/09-component-build-sheet.md#evidence-from-the-first-capture-run).
