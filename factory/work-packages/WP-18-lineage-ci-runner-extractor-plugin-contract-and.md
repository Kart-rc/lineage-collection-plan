# WP-18: lineage-ci runner, extractor plugin contract and repository onboarding

Wave 1 · family platform · start level 2 · limits: 6 build attempts, 1 working day, cost recorded

**Serves:** XC-7, XC-8, IN-1, IN-7, IA-1, IA-6  
**Depends on:** WP-10, WP-11

## Scope

The one step every onboarded repository runs. It validates .lineage.yaml, detects units through registered extractors, hashes them, skips unchanged units, runs the rest under a deadline, emits envelope v2 to production or to the PR overlay, writes a unit manifest, and fails open. It ships a stub extractor and the conformance suite (D39).

## Inputs

- factory/specs/build-collection/interfaces/extractor-plugin.md
- factory/specs/build-collection/interfaces/lineage-repo.schema.json
- factory/specs/build-collection/interfaces/unit-manifest.schema.json

## Outputs

- planned:lineage-ci/ (CLI
- GitHub Action wrapper
- stub extractor
- conformance suite)

## Must hold

- The CLI is the product; the GitHub Action only calls it, so any CI system can run the same command
- Never fails a build because of its own errors or an unreachable platform; only the contract gate may fail a build (IA-5)
- Extractors get schemas only through ctx.schema_at as of the commit; the runner enforces no other network access
- Weights are set by the runner from parameters.yaml, never by an extractor

## Done when

- `lineage-ci validate` accepts 2 of 2 onboarding examples and rejects 5 of 5 invalid ones, each with a message that names the field to fix
- With the stub extractor, a merged scan of the demo at 3.1.0 lists one unit per configured service and schema (16) in a manifest that validates; a re-scan of the same commit re-extracts 0 units
- A PR scan that changes only src/checkout/main.go re-extracts 1 unit and marks 15 unchanged, and 100% of its events go to the overlay keyed by repository and PR
- Runner overhead, excluding extractor time, is 60 seconds or less at p95 over 20 scans
- With the evidence topic unreachable, 100% of fault scenarios exit 0, write outcome unavailable and raise an alert
- The same scan gives byte-identical normalized scan content as a GitHub Action and as a plain container command (1 of 1 non-GitHub runner), excluding only started, finished and per-unit duration_ms; full manifests retain measured timings
- The stub extractor passes 100% of the conformance suite
- Every visible scenario traced to the requirements above passes
- Holdout pass rate at or above the family rate in `factory/parameters.yaml`, where the family has holdout scenarios
- `python3 code/spec_pack.py --check` reports 0 errors

## Fixtures

- `fixtures/otel-demo-3.1.0/onboarding/`
- `fixtures/otel-demo-3.1.0/onboarding/invalid/`

## Requirements

- **XC-7**: When a repository's default branch holds a valid `.lineage.yaml` and its CI runs the `lineage-ci` step, the system shall treat the repository as onboarded, complete a first scan of its default branch within 1 hour, and scan every later pull request and merge. If the file is invalid, then the step shall name the failing field and still pass the build. Scenarios: S-BC-01, S-BC-02, S-BC-04.
- **XC-8**: Every extractor shall implement the extractor plugin contract and pass its conformance suite before the runner loads it, so that adding a technology requires no change to the runner. Scenarios: S-BC-05, S-BC-06.
- **IN-1**: When a commit lands on a default branch, the system shall re-extract only the units whose content hash, input schema hash or extractor version changed. Scenarios: S-BC-03, S-IN-01.
- **IN-7**: While a pull request is open, the system shall hold its static evidence in an overlay keyed by repository and PR number, invisible to production impact and RCA queries. Scenarios: S-BC-03, S-IN-08.
- **IA-1**: When a pull request opens or updates in an onboarded repository, the system shall post an impact report within 5 minutes at the 95th percentile. Scenarios: S-BC-03, S-IA-07.
- **IA-6**: If the lineage platform is unavailable, then the check shall pass with a "lineage check unavailable" comment and raise an alert. Scenarios: S-BC-04, S-IA-08.
