# Requirements: build-collection

Rendered from `factory/specs/requirements.yaml`. EARS phrasing; IDs as in doc 06.

| Id | Requirement | Verified by | Work packages | Visible scenarios |
| --- | --- | --- | --- | --- |
| XC-7 | When a repository's default branch holds a valid `.lineage.yaml` and its CI runs the `lineage-ci` step, the system shall treat the repository as onboarded, complete a first scan of its default branch within 1 hour, and scan every later pull request and merge. If the file is invalid, then the step shall name the failing field and still pass the build. | Onboarding scenarios on the demo monorepo and the dbt project; invalid onboarding fixtures | WP-18 | S-BC-01, S-BC-02, S-BC-04 |
| XC-8 | Every extractor shall implement the extractor plugin contract and pass its conformance suite before the runner loads it, so that adding a technology requires no change to the runner. | Plugin conformance suite; the stub and dbt extractors loaded by an unchanged runner | WP-18 | S-BC-05, S-BC-06 |
