# Oracle

PROTECTED: only people merge changes here (constitution, protected paths). Signed at gate G3 on 28 November 2026; each oracle file is pinned by hash in [`../gates/G3-2026-11-28.md`](../gates/G3-2026-11-28.md).

The oracle is what makes "correct" machine-checkable. On the reference slice its parts are:

| Part | Where | Gate |
| --- | --- | --- |
| Golden graph: 23 service edges, 36 field edges, 8 flag-gated edges, 20 flag edges, 5 must-not-flow rules, with a citation for each | `fixtures/otel-demo-3.1.0/golden-graph.json`, from `code/reference_slice.py` | G3 |
| Golden edges for the thin dbt model: 30 direct, 5 indirect, hand-written from the SQL | `fixtures/otel-demo-3.1.0/dbt/golden-dbt.json` | G3 |
| Change replay, visible: C1 to C7 from history and the twin, C8 to C13 authored | `fixtures/otel-demo-3.1.0/change-replay.json` | G3 |
| Incident replay, visible: I1 to I10 run in the twin | `fixtures/otel-demo-3.1.0/incident-scenarios.json` | G3 |
| Checks and contracts | `fixtures/otel-demo-3.1.0/checks.yaml`, `contracts/` | G3 |
| Holdout corpora | Outside this repository; see `holdout/README.md` | G3 |
| Harness `lineage-eval` | `harness/` (WP-04), built from `code/observed_edges.py` and `code/run_checks.py` | G2 at level 2, every line read |
| Gate policies as code | `policies/` (WP-34) | G1 |

Corpus targets are in `factory/parameters.yaml` under `corpora`: at least 20 changes and 20 incidents, a third of each family held out.
