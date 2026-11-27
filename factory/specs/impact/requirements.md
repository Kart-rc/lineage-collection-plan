# Requirements: impact

Rendered from `factory/specs/requirements.yaml`. EARS phrasing; IDs as in doc 06.

| Id | Requirement | Verified by | Work packages | Visible scenarios |
| --- | --- | --- | --- | --- |
| IA-1 | When a pull request opens or updates in an onboarded repository, the system shall post an impact report within 5 minutes at the 95th percentile. | Timing in the twin; production probe | WP-03, WP-33 | S-IA-07 |
| IA-2 | The report shall list each changed element with its change kind: added, removed, renamed, retyped, nullability changed, logic changed, or row set changed. | Change-kind fixtures per extractor | WP-21, WP-32 | S-IA-01, S-IA-06 |
| IA-3 | The system shall classify each change as breaking, potentially breaking, non-breaking or unknown. It shall classify a change that leaves the normalized expression unchanged as non-breaking, and a change in a unit it cannot parse as unknown, which is reported and treated as potentially breaking. | Classification fixtures, including formatting-only diffs and an opaque unit | WP-32 | S-IA-01, S-IA-02, S-IA-03, S-IA-04, S-IA-05, S-IA-06 |
| IA-4 | The report shall list downstream elements and assets by hop with owner, tier, edge state and confidence, following direct dependencies for value impact and reporting indirect dependencies separately as row-set impact. | Change C1 scenario (zip_code retyped); direct and indirect fixtures from the thin dbt model | WP-17, WP-31 | S-IA-01, S-IA-03 |
| IA-5 | While the gate is in block mode, the system shall fail the check only when a tier 1 contract element with confirmed downstream readers is removed, renamed or retyped without a version bump or sign-off from those readers' owners. | Gate policy scenarios | WP-34 | S-XC-07, S-XC-08, S-IA-01, S-IA-06 |
| IA-6 | If the lineage platform is unavailable, then the check shall pass with a "lineage check unavailable" comment and raise an alert. | Fail-open scenario | WP-33, WP-34, WP-53 | S-IA-08 |
| IA-7 | The report shall offer a "this is wrong" action per row, and a disputed edge shall drop to candidate until reviewed. | Feedback scenario | WP-12, WP-16, WP-33 | S-IA-09 |
| IA-8 | On the change replay corpus the report shall list at least 8 of every 10 consumers that actually broke. | `lineage-eval replay changes` | WP-02, WP-04, WP-33 | S-IA-01, S-IA-06 |
| IA-9 | The system shall expose the same impact query through an API that coding agents can call before a pull request exists. | API contract test | WP-31, WP-51 | S-IA-10 |
