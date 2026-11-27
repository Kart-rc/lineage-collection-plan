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

## What it showed

See [doc 09](../../../docs/09-component-build-sheet.md#evidence-from-the-first-capture-run).
