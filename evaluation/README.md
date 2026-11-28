# Evaluation harness candidate

This directory and `src/lineage/evaluation.py` implement reviewable WP-02/WP-04 tooling. They are outside the protected oracle. They do not approve G3, G4, a holdout corpus, or a release. The pinned oracle, requirements, thresholds, and gate records remain unchanged.

The CLI returns `0` for a passing measured check and `2` for blocked evidence or a failed bar. Invalid CLI syntax also returns `2`. JSON is canonical: sorted keys, two-space indentation, a trailing newline, and no wall-clock timestamp. Repeated runs on identical inputs produce identical bytes.

## Commands

Install the project and its test extras in an isolated environment with `python -m pip install -e '.[test]'`. Run these from the checkout:

```sh
lineage-eval gate verify --output /tmp/oracle-verification.json
lineage-eval custody --output /tmp/custody.json
lineage-eval score --candidate /absolute/path/candidate-graph.json --output /tmp/score.json
lineage-eval replay changes --candidate /absolute/path/change-outcomes.json --output /tmp/changes.json
lineage-eval replay incidents --candidate /absolute/path/incident-outcomes.json --output /tmp/incidents.json
lineage-eval release --candidate /absolute/path/candidate-bundle.json --output /tmp/accuracy.json --record /tmp/G4-candidate.md
```

`release --baseline /absolute/path/baseline-bundle.json` compares to a baseline. Without a baseline, only no-loss comparison is skipped. Required replay sources, floors, applicable hard zeros, timing evidence, and holdout requirements still apply. A baseline bundle does not establish that it was the last approved release; independent verification of its G4 approval remains a blocker.

The generated Markdown contains exactly ten G4 sections. A person supplies the eleventh, **Decision**, after reviewing all evidence. Keep the candidate record outside `factory/gates/` until that human action; the repository checker requires all eleven sections for an actual gate record. The accuracy report's full SHA-256 is embedded in the Markdown, and all eight G3 file hashes are computed in full and checked against the published G3 prefixes.

## Candidate observations and expected truth

`candidate-bundle.schema.json` defines release inputs. Candidate graphs contain `service_edges`, `field_edges`, `gated_field_edges`, `flag_edges`, and/or `dataset_edges`. Service, flag, and dataset edges require `from`, `to`, and their actual `type`. Field edges require `from`, `to`, `class`, and `subtype`; identity also includes relationship type (`DERIVES` by default), masking (`false` by the approved envelope default), and condition. Gated edges explicitly supply their condition; the approved collector transforms use null because they are unconditional. Missing class/subtype is rejected; changing masking or subtype loses the original semantic edge.

Field accuracy covers both approved oracles: 36 reference edges plus 35 dbt edges, for 71 total. Eight flag-gated edges, 20 flag edges, and the dbt dashboard exposure are reported separately. Results include per-edge-type and per-hop precision/recall. Release scope applies the WP-20 dbt 90% floor (direct and indirect separately), WP-24 accounting 95%, WP-23 checkout 90%, and WP-28 dashboard exposure floor when carried. BL-6 includes all approved reference field hops; missing complementary oracle coverage remains unavailable. Service accuracy excludes flagd control calls. Must-not-flow walks candidate field and gated edges transitively, including latent edges; it does not fill missing candidate edges from the oracle.

Change outcomes are arrays of `{id, readers, gate}`. Incident outcomes are arrays of `{id, detected, ranking, minutes_to_detect}`, where `ranking` contains cause identities in the candidate's actual order. Cause identities are the public scenario's flag or stopped service, such as `paymentFailure` or `accounting`. Undetected incidents have an empty ranking and a null detection time. Precomputed `passed`, `rank`, `precision`, or `recall` fields are rejected. The harness independently loads the pinned public truth. Duplicate/unknown case IDs and malformed outcomes fail validation.

A missed input is **unavailable**, not a successful empty result. Partial replay results show coverage and name missing visible cases. Incident no-loss cases separately retain detection, rank-first, and rank-top-three success. Therefore moving a true cause from first to second loses a case even if aggregate IR-5 scores remain above both floors. Any baseline-passed golden edge or change that disappears is similarly named.

## Release evidence binding

Every source in `sources` points to an actual local JSON artifact with a SHA-256, commit, run ID, exact start/end timestamps, and event count. Paths are resolved relative to the checkout unless absolute. The artifact shape is:

```json
{
  "run_id": "the-actual-run-id",
  "commit": "the-actual-candidate-commit",
  "started_at": "2026-11-28T00:00:00Z",
  "ended_at": "2026-11-28T00:01:00Z",
  "events": [
    {"kind": "graph", "value": {"service_edges": [], "field_edges": []}}
  ]
}
```

This structural example is not evidence. The runner must write its actual results. Observation event kinds are `graph`, `changes`, `incidents`, `timing`, `payload_scan`, `fault_scenarios`, and `rebuild`. Their `value` must exactly match the associated bundle object. For timings and scans, the object's `source_run_id` must also match. A missing file, digest mismatch, event-count mismatch, mismatched commit/time span, or unbound value blocks the release. This checks provenance consistency; it cannot certify a runner's honesty. Trusted runner identity, package-specific conformance, and human approval are independent evidence.

Required source kinds before slice 2 are `recorded_twin_captures`, `recorded_corpora`, and `fresh_twin_run`. From slice 2, `one_day_of_production_evidence` is additionally required and must span at least 24 hours. Recorded replay artifacts must come from running the candidate on real recorded inputs. Relabeling an old summary or synthetic test artifact as a replay does not satisfy the historical acceptance check.

Timings are nearest-rank p95 over actual `samples_seconds`, bound to a fresh twin artifact, and compared only to the configured requirement bar. Payload/fault zero counts are summed from named observations bound to a fresh twin artifact. A supplied zero without bound observations remains unavailable. Must-not-flow violations are always reported when observed; a purported zero requires bound graph evidence. Hard zeros and timing requirements are applied only to carried work packages. Missing raw data, private results, or package-specific done-when/scenario checks remain explicit blockers. Neo4j Community local validation can be supplied as local implementation evidence; this harness does not require or claim a stage Neptune deployment.

## Historical capture reproduction

The repository contains summary JSON and change events for 27 November, but not the raw traces or metrics. These commands require real capture locations:

```sh
lineage-eval score --capture /absolute/path/raw-run-1 --output /tmp/raw-run-1-score.json
lineage-eval replay incidents --capture /absolute/path/raw-run-1 --events /absolute/path/change-events.jsonl --candidate-graph /absolute/path/candidate-runtime-graph.json --output /tmp/raw-run-1-incidents.json
```

The score command reads `traces.jsonl` through `code/observed_edges.py`. Incident replay reads `metrics.jsonl` through `code/run_checks.py` with an explicitly supplied candidate graph containing `service_edges` and `flag_edges`. The prototype's truth-derived rank is discarded and recomputed from its candidate ordering against separate pinned truth. A run containing only I1 reports the other public incidents as unavailable; it is not full-corpus acceptance. These commands do not accept `observed-edges.json`, `checks-run.json`, or `incident-replay.json` as raw capture substitutes. Until actual run-1 data is supplied and reviewed, the WP-04 historical reproduction remains blocked.

The shared trace prototype projects supported SQL to table/column names using a scoped Postgres parser. It suppresses the parser's raw-input warning hook without changing shared logging or stderr. Unsupported SQL, malformed statements, and missing parser support produce no database mappings; there is no regex fallback over potentially sensitive string literals. SQL values never appear in evaluation reports or parser diagnostics. Incident replay does not parse SQL attributes.

## WP-02 custody

`custody` reads the existing public corpora and reports visible counts, family coverage, and missing executable base/trigger/outcome metadata. An optional `--visible-metadata` sidecar may add approved case IDs' family, base revision, a real trigger artifact `{path, sha256}`, and `expected_outcome: {oracle_case: "C1"}` (or the matching incident ID). It references existing truth rather than replacing it. It does not add cases or change expected results. Owners must supply missing case authoring and sign-off through the protected-oracle review process.

Private aggregate validation checks minimum corpus counts, at least seven changes and seven incidents privately held, at least one third of every family's cases privately held, all configured family categories, signatures, independent provenance, candidate commit, exact oracle digest map, and the pinned aggregate digest. The approved `0.33` parameter is interpreted together with the constitution's exact one-third rule. These checks never read or generate holdout cases. See [the private job contract](private-job-contract.md).

## Validation and limits

`python -m pytest -q tests/test_evaluation.py` runs deterministic public synthetic regressions. The test-only baseline copies public truth to create controlled faults; it is explicitly not operational or holdout evidence. The suite covers dropped edges above the floor, forbidden flow, rank-first loss above aggregate floors, missing evidence, raw-source rejection, private output leakage rejection, source digest binding, family coverage, and first-release behavior.

This implementation measures supported metrics and generates evidence recommendations. Full work-package done-when execution and human conformance review are not implemented by asserting a boolean in a candidate file; those remain blockers. Generated records do not declare service levels held. Human oracle review is still required before this candidate could become the protected evaluation harness.
