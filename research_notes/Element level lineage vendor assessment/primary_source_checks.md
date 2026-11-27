# Primary-source checks (coordinator)

Read on 2026-11-26. Web search ran out of budget for this session and most documentation hosts are blocked by the session's network policy, so the other notes in this folder rest largely on search-result snippets. The items below are different: each file was fetched in full from the project's own public repository (raw.githubusercontent.com, default branch) and the quoted text was read directly. Treat these as the highest-confidence findings in the folder. Where another note disagrees with an item here, this file wins.

## 1. OpenLineage column lineage facet (spec 1-2-0)

Sources: `OpenLineage/OpenLineage` `spec/facets/ColumnLineageDatasetFacet.json` and `website/docs/spec/facets/dataset-facets/column_lineage_facet.md`.

- Schema id: `https://openlineage.io/spec/facets/1-2-0/ColumnLineageDatasetFacet.json`.
- Two parts. `fields`: "Column level lineage that maps output fields into input fields used to evaluate them." `dataset`: "Column level lineage that affects the whole dataset. This includes filtering, sorting, grouping (aggregates), joining, window functions, etc."
- Each input field carries `transformations[]` with four fields: `type`, `subtype`, `description`, `masking`. Type: "Allowed values are: DIRECT, INDIRECT".
- INDIRECT is defined as: "output column value is impacted by the value of `inputField` column, but it's not derived from it."
- Subtypes documented: DIRECT has `IDENTITY` ("output value is taken as is from the input"), `TRANSFORMATION`, `AGGREGATION` ("output value is aggregation of source values from multiple input rows"). INDIRECT has `JOIN`, `GROUP_BY`, `FILTER`, `SORT`, `WINDOW`, `CONDITIONAL` ("input value is used in `IF`, `CASE WHEN` or `COALESCE` statements").
- Spark: dataset-level indirect lineage needs `spark.openlineage.columnLineage.datasetLineageEnabled=True`. The default is `False`, which moves every dataset-level dependency into `fields`, "producing almost a cartesian product of all dataset fields. This is very inefficient." The docs recommend turning it on.
- Implication for a build: store indirect dependencies once per target dataset, not per target column.

## 2. OpenLineage Flink 2 integration: no column lineage at runtime

Source: `OpenLineage/OpenLineage` `website/docs/integrations/flink/flink2.md`.

- "Unfortunately, lineage interfaces in Flink 2.x do not provide column level lineage information. In general, this may be difficult to extract for the transformations defined through the programming language. However, it is possible to extract column level lineage information for Flink SQL jobs."
- The same section points to an Apache Flink pull request (apache/flink#26089) as "a potential extension to Flink to make it available". So as read today it is a proposal, not shipped behaviour.
- The Flink 2 integration supports Flink SQL at dataset level ("it supports Flink SQL, which was not possible with the previous version").
- Confirms the earlier finding in `docs/04-research-appendix.md`: field detail on the Flink hop has to come from static analysis of the SQL plan, from schemas, or from declared mappings.

## 3. dbt column-level lineage (dbt platform Catalog, formerly Explorer)

Source: `dbt-labs/docs.getdbt.com` `website/docs/docs/explore/column-level-lineage.md`.

- Plan gate: "Requires an Enterprise or Enterprise+ plan".
- Direct dependencies only: "Column-level lineage reflects the lineage from `select` statements in your models' SQL code. It doesn't reflect other usage like joins and filters."
- "Column evolution lens" labels a column as transformed versus reused (Passthrough or Rename) and shows the formula. "The transformation type and formula appear after you update your project and a job runs in your production or staging environment."
- Limits: "Column-level lineage relies on SQL parsing. Errors can occur when parsing fails or a column's origin is unknown (like with JSON unpacking, lateral joins, and so on)." Python models: "it's not possible to parse and determine the lineage."

## 4. SQLMesh change categories (breaking and non-breaking)

Source: `TobikoData/sqlmesh` `docs/concepts/plans.md`.

- A plan lists directly modified models and "indirectly modified" downstream models.
- Breaking: "it and its downstream dependencies will be backfilled." Example given: "adding or modifying a model's `WHERE` clause is a breaking change".
- Non-breaking: the directly modified model is backfilled "but its downstream dependencies will not".
- "If any downstream models contain a `select *` from the model, SQLMesh attempts to infer breaking status on a best-effort basis."
- Conflicts resolve to "the most conservative category (breaking)".
- Each changed model gets a new snapshot with a unique fingerprint. This is the published pattern for content-addressed, incremental re-evaluation.

## 5. DataHub (open source docs)

Sources: `datahub-project/datahub` `docs/lineage/sql_parsing.md`, `docs/lineage/openlineage.md`, `docs/act-on-metadata/impact-analysis.md`.

- "DataHub's SQL parser is built on top of sqlglot". Vendor-stated accuracy: "In our benchmarks, the DataHub SQL parser generates lineage with 97-99% accuracy and outperforms other SQL parsers by a wide margin." The benchmark itself is not in the doc.
- Not supported: scalar UDFs ("We will generate lineage pointing at the columns that are inputs to the UDF, but will not be able to understand the UDF itself"), table-valued functions, "Snowflake's multi-table inserts", "Multi-statement SQL / SQL scripting".
- Limitation: "`MERGE INTO` statements - We don't generate column-level lineage for these." Also, stale schema information in DataHub reduces column-lineage accuracy.
- OpenLineage: a REST endpoint accepts OpenLineage events, with `capture-column-level-lineage` defaulting to `true`. For Spark and Airflow the docs recommend DataHub's own plugins over the generic endpoint.
- Impact analysis: "available via the DataHub UI and GraphQL endpoints, supporting manual and automated workflows", filtered by degree of dependency, exportable to CSV. Nothing in this doc describes a pull-request integration or a point-in-time view.

## 6. Marquez

Source: `MarquezProject/marquez` `README.md`.

- "Marquez is an LF AI & Data Foundation Graduated project under active development".
- The README's compatibility table lists `0.50.0` (dated 2024-10-23 in the changelog link) as the RECOMMENDED release and shows only `UNRELEASED` above it. As read on 2026-11-26 that means no tagged release for about two years. Treat Marquez as a reference backend with slow release cadence.

## 7. Recce

Source: `DataRecce/recce` `README.md`.

- Positioning: "Helping data teams preview, validate, and ship data changes with confidence." Works on a dbt project; diffing needs "two environments to compare against".
- Use: "Select nodes in the lineage to perform Checks (diffs) as part of your impact assessment during development or PR". Model and column level diff are shown in the README.

## 8. Factory and spec-driven development methods

Sources: `strongdm/attractor` `README.md` and `attractor-spec.md`; `github/spec-kit` `README.md`; `awslabs/aidlc-workflows` `README.md`.

- **StrongDM Attractor.** The repository "contains NLSpecs to build your own version of Attractor to create your own software factory." NLSpec: "a human-readable spec intended to be directly usable by coding agents to implement/validate behavior." The repository ships three specs and no code; the README tells the reader to hand the repository URL to a coding agent to implement it. Attractor itself is "a DOT-based pipeline runner that uses directed graphs ... to orchestrate multi-stage AI workflows. Each node in the graph is an AI task (LLM call, human review, conditional branch, parallel fan-out, etc.)", with checkpoint and resume after each node and a human-in-the-loop pattern.
- **GitHub Spec Kit.** Flow: `/speckit-constitution` once per project, then `/speckit-specify`, `/speckit-plan`, `/speckit-tasks`, `/speckit-implement`, `/speckit-converge` per feature. "Repeat implement and converge until convergence reports `Converged`." Each step is run "one at a time, reviewing each result before continuing."
- **AWS AI-DLC workflows (v2.11.5, MIT-0).** "AI-DLC (AI-Driven Development Life Cycle) turns AI coding assistants into structured, verifiable software-delivery workflows." Runs in Claude Code, Kiro CLI, Kiro IDE, Codex CLI, Cursor, opencode and GitHub Copilot. Stated contents: "5 phases and 33 stages from initialization through operation", "14 agents: 11 domain experts, 2 reviewers, and an adaptive composer", "11 workflow profiles", "Human approval gates and source-bound review evidence", "134-event audit trail plus persistent state, team knowledge, and learned rules".

## What could not be checked

- Release dates and star counts through the GitHub API (not reachable from this session).
- Any vendor documentation host (IBM, Collibra, Informatica, Atlan, Alation, Snowflake, Databricks, AWS, Google, Microsoft, Monte Carlo, Datafold and others). Claims about these in the other notes come from search snippets and should be re-read at the source before they are used in a contract or an ADR.
