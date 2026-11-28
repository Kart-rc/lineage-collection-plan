# Factory spec pack

What the agents build from and what the harness grades against, for the reference slice in [doc 07](../docs/07-reference-slice-otel-demo.md). The layout is the one doc 06 specifies under "Spec pack layout". Status: **approved at gate G1 on 28 November 2026** at commit `b86111d` ([gate record](gates/G1-2026-11-28.md); decisions D33 to D37 in [doc 08](../docs/08-build-decisions.md)). A change to a protected path now needs a new G1 record. The oracle was signed at gate G3 the same day ([record](gates/G3-2026-11-28.md)); a change to it needs a new G3 record.

```text
python3 code/spec_pack.py --check     # must report 0 errors before any work package starts
python3 code/spec_pack.py --write     # re-render the markdown after editing a YAML source
```

| Path | What it holds | Edited by |
| --- | --- | --- |
| [`constitution.md`](constitution.md) | Rules every agent run loads, protected paths, definition of done | People (protected) |
| [`parameters.yaml`](parameters.yaml) | Every number the build is judged by: weights, states, thresholds, the RCA score, holdout rates, corpus sizes | People (protected) |
| [`specs/requirements.yaml`](specs/requirements.yaml) | The 43 requirements from doc 06, verification re-targeted to the reference slice; rendered per capability as `specs/<capability>/requirements.md` with the work packages and scenarios that cover each | People at G1 |
| [`specs/evidence/interfaces/envelope-v2.schema.json`](specs/evidence/interfaces/envelope-v2.schema.json) | The evidence envelope: evidence, check results and change events. Examples in `specs/evidence/examples/`, including deliberately invalid ones | People at G1 |
| [`specs/changes/interfaces/lineage-changes.schema.json`](specs/changes/interfaces/lineage-changes.schema.json) | One event per material edge change | People at G1 |
| [`specs/query-api/interfaces/openapi.yaml`](specs/query-api/interfaces/openapi.yaml) | `/impact`, `/upstream`, `/diff`, `/explain` | People at G1 |
| `specs/*/scenarios/visible/*.feature` | Visible scenarios, tagged with the requirements they trace | People write; agents read |
| [`specs/build-collection/interfaces/`](specs/build-collection/interfaces/extractor-plugin.md) | The `lineage-ci` runner, the extractor plugin contract, the `.lineage.yaml` onboarding file and the unit manifest (D39) | People at G1 |
| [`work-packages/`](work-packages/README.md) | Done-when for all 40 work packages: one YAML source, one rendered file each | People at G1 |
| [`oracle/`](oracle/README.md) | Index of the golden graph, replay corpora, checks and contracts; the harness and gate policies land here | People (protected) |
| [`oracle/holdout/README.md`](oracle/holdout/README.md) | Custody rules. The holdout itself is never in this repository | People (protected) |
| [`gates/`](gates/) | One record per gate decision: who approved what, at which commit | People |

## What is not here yet, and which work package brings it

- The harness `lineage-eval` (WP-04), built from `code/observed_edges.py` and `code/run_checks.py`.
- The twin's one-command start with the lineage platform beside the demo (WP-03). Today the demo runs with the files in `fixtures/otel-demo-3.1.0/run/`.
- The holdout corpora (WP-02), written by people outside this repository.
- Golden edges for the complement repository (WP-01), needed by WP-22 and WP-25.
- `runs/`, one record per agent run, created by the first run.
