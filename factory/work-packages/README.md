# Work packages

Rendered from `work-packages.yaml` by `python3 code/spec_pack.py --write`. Edit the YAML, not these files.

| Id | Work package | Wave | Level | Serves | Depends on | Done when |
| --- | --- | --- | --- | --- | --- | --- |
| [WP-00](WP-00-constitution-and-spec-pack-skeleton.md) | Constitution and spec pack skeleton | 0 | people | - | - | 3 |
| [WP-01](WP-01-golden-graph-at-element-level-as-fixtures.md) | Golden graph at element level, as fixtures | 0 | people | BL-1, BL-6 | WP-00 | 3 |
| [WP-02](WP-02-change-and-incident-replay-corpora-visible-and-h.md) | Change and incident replay corpora, visible and holdout split | 0 | people | IA-8, IR-5 | WP-01 | 3 |
| [WP-03](WP-03-twin-of-the-slice.md) | Twin of the slice | 0 | 2 | IN-10, IA-1 | WP-00 | 3 |
| [WP-04](WP-04-scoring-harness-lineage-eval.md) | Scoring harness lineage-eval | 0 | 2 | BL-6, BL-7, IA-8, IR-5 | WP-01, WP-02 | 7 |
| [WP-10](WP-10-urn-library-with-nested-field-paths.md) | URN library with nested field paths | 1 | 2 | BL-1 | WP-00 | 2 |
| [WP-11](WP-11-envelope-v2-schema-and-emit-library.md) | Envelope v2 schema and emit library | 1 | 2 | BL-2, BL-4, XC-1, XC-2, XC-3 | WP-10 | 3 |
| [WP-12](WP-12-merge-and-scorer-with-unit-owned-static-evidence.md) | Merge and scorer with unit-owned static evidence; conditional edges with a latent state | 1 | 2 | BL-5, IN-2, IN-8, IN-9, IA-7, XC-2 | WP-11 | 4 |
| [WP-13](WP-13-bitemporal-graph-writer-and-as-of-reads-on-neptu.md) | Bitemporal graph writer and as-of reads, on Neptune over Bolt with Neo4j standing in locally | 1 | 2 | BL-7, IN-4, IN-5, IN-10, IR-2 | WP-12 | 3 |
| [WP-14](WP-14-lineage-diff-and-the-lineage-changes-stream.md) | Lineage diff and the lineage.changes stream | 1 | 2 | IN-6 | WP-13 | 2 |
| [WP-15](WP-15-identity-resolver-at-element-level-never-aliasin.md) | Identity resolver at element level, never aliasing an IP | 1 | 2 | BL-1 | WP-10 | 2 |
| [WP-16](WP-16-daily-reconciler-and-owner-queues.md) | Daily reconciler and owner queues | 1 | 2 | IA-7 | WP-12, WP-17 | 2 |
| [WP-17](WP-17-owner-and-tier-overlay-from-the-catalog-file-and.md) | Owner and tier overlay from the catalog file and service criticality | 1 | 2 | IA-4, XC-5 | WP-10 | 2 |
| [WP-18](WP-18-lineage-ci-runner-extractor-plugin-contract-and.md) | lineage-ci runner, extractor plugin contract and repository onboarding | 1 | 2 | XC-7, XC-8, IN-1, IN-7, IA-1, IA-6 | WP-10, WP-11 | 7 |
| [WP-19](WP-19-service-edge-builder-trace-walk-topic-joins-ingr.md) | Service edge builder: trace walk, topic joins, ingress logs | 1 | 2 | BL-6, XC-3 | WP-11, WP-15 | 3 |
| [WP-20](WP-20-dbt-and-sql-extractor.md) | dbt and SQL extractor | 2 | 3 | BL-2, BL-3, BL-4, BL-5, IN-3 | WP-10, WP-11, WP-18 | 3 |
| [WP-21](WP-21-protobuf-schema-differ-and-registry-watcher.md) | Protobuf schema differ and registry watcher | 2 | 3 | BL-1, IN-3, IA-2 | WP-10, WP-11, WP-18 | 3 |
| [WP-22](WP-22-stream-job-extractor-pyflink-code-and-the-declar.md) | Stream job extractor: PyFlink code and the declared feature registry first | 2 | 3 | BL-3, BL-4 | WP-11, WP-18 | 1 |
| [WP-23](WP-23-service-producer-and-consumer-field-scanner.md) | Service producer and consumer field scanner | 2 | 3 | BL-2, BL-3, BL-4 | WP-10, WP-11, WP-21, WP-18 | 3 |
| [WP-24](WP-24-sink-and-orm-writer-extractor-c-entity-framework.md) | Sink and ORM writer extractor, C# Entity Framework first | 2 | 3 | BL-2, BL-3 | WP-10, WP-11, WP-18 | 2 |
| [WP-25](WP-25-feature-repository-and-training-config-extractor.md) | Feature repository and training config extractor | 2 | 3 | BL-3 | WP-11, WP-22, WP-18 | 1 |
| [WP-26](WP-26-access-history-collector-at-column-level-postgre.md) | Access-history collector at column level: Postgres first, then Snowflake and Databricks | 2 | 3 | BL-3, XC-1 | WP-11, WP-15 | 3 |
| [WP-27](WP-27-openlineage-ingestion-with-column-facets.md) | OpenLineage ingestion with column facets | 2 | 3 | XC-4 | WP-11 | 1 |
| [WP-28](WP-28-bi-metadata-extractor.md) | BI metadata extractor | 2 | 3 | BL-3 | WP-11, WP-18 | 2 |
| [WP-29](WP-29-model-assisted-extractor-for-opaque-units-with-a.md) | Model-assisted extractor for opaque units, with a verifier | 2 | 2 | BL-4, XC-6 | WP-11, WP-23, WP-18 | 3 |
| [WP-30](WP-30-change-detectors-and-unit-invalidation.md) | Change detectors and unit invalidation | 3 | 3 | IN-1, IN-3, IN-10 | WP-12, WP-20, WP-21, WP-18 | 3 |
| [WP-31](WP-31-pr-overlay-and-impact-query-api.md) | PR overlay and impact query API | 3 | 3 | IN-7, IA-4, IA-9 | WP-13, WP-14, WP-18 | 3 |
| [WP-32](WP-32-change-classifier.md) | Change classifier | 3 | 3 | IA-2, IA-3 | WP-21, WP-20 | 2 |
| [WP-33](WP-33-pr-bot-in-warn-mode-with-feedback.md) | PR bot in warn mode with feedback | 3 | 3 | IA-1, IA-6, IA-7, IA-8 | WP-31, WP-32 | 3 |
| [WP-34](WP-34-contract-gate-in-block-mode.md) | Contract gate in block mode | 3 | 2 | IA-5, IA-6 | WP-31, WP-32, WP-17 | 3 |
| [WP-39](WP-39-check-runner-for-the-twin-s-checks.md) | Check runner for the twin's checks | 4 | 3 | IR-1 | WP-11 | 3 |
| [WP-40](WP-40-dq-and-contract-result-ingestion-on-elements.md) | DQ and contract result ingestion on elements | 4 | 3 | IR-1, IR-3 | WP-39, WP-34 | 1 |
| [WP-41](WP-41-change-event-timeline-flag-changes-join-through.md) | Change-event timeline; flag changes join through flag edges | 4 | 3 | IR-2, IR-4 | WP-11, WP-12 | 2 |
| [WP-42](WP-42-rca-ranker-narrow-to-the-failing-callee-then-ran.md) | RCA ranker: narrow to the failing callee, then rank | 4 | 3 | IR-1, IR-2, IR-3, IR-4, IR-5 | WP-13, WP-40, WP-41 | 3 |
| [WP-43](WP-43-remediation-planner-and-circuit-breaker.md) | Remediation planner and circuit breaker | 4 | 2 | IR-6, IR-7, IR-8 | WP-42 | 3 |
| [WP-44](WP-44-mttd-and-mttr-recorder.md) | MTTD and MTTR recorder | 4 | 3 | IR-9 | WP-42 | 2 |
| [WP-50](WP-50-catalog-projections-from-lineage-changes.md) | Catalog projections from lineage.changes | 5 | 3 | XC-4 | WP-14, WP-27 | 1 |
| [WP-51](WP-51-read-api-and-agent-tool-server.md) | Read API and agent tool server | 5 | 3 | IA-9, XC-2, XC-5 | WP-31, WP-42 | 3 |
| [WP-52](WP-52-terraform-modules-and-service-roles.md) | Terraform modules and service roles | 5 | 2 | XC-6 | WP-00 | 2 |
| [WP-53](WP-53-dashboards-alarms-and-runbooks.md) | Dashboards, alarms and runbooks | 5 | 3 | XC-3, IA-6 | WP-52 | 2 |
