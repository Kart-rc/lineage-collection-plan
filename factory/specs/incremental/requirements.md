# Requirements: incremental

Rendered from `factory/specs/requirements.yaml`. EARS phrasing; IDs as in doc 06.

| Id | Requirement | Verified by | Work packages | Visible scenarios |
| --- | --- | --- | --- | --- |
| IN-1 | When a commit lands on a default branch, the system shall re-extract only the units whose content hash, input schema hash or extractor version changed. | Unit-invalidation scenarios; extractor call count | WP-30 | S-IN-01 |
| IN-3 | When a schema version is registered or a tier 1 table's DDL changes, the system shall publish a schema-change event and re-extract every unit that reads the changed dataset. | `SELECT *` scenario: a column added to accounting.shipping reaches stg_shipping | WP-20, WP-21, WP-30 | S-IN-04 |
| IN-6 | The system shall produce a lineage diff between any two times or commits: elements and edges added, removed and changed, with the evidence that caused each change. | Diff scenarios against hand-written expected diffs for changes C3, C4, C5 and C7 | WP-14 | S-IN-07, S-IN-12, S-IN-13 |
| IN-7 | While a pull request is open, the system shall hold its static evidence in an overlay keyed by repository and PR number, invisible to production impact and RCA queries. | Overlay isolation scenario | WP-31 | S-IN-08 |
| IN-10 | The system shall make an edge visible within 15 minutes of the merge or run that produced it, at the 95th percentile. | Freshness probe on stage replay | WP-03, WP-13, WP-30 | S-IN-11 |
