# Addendum: shift-left and observability vendor gaps in element-level lineage (state as of 26 Nov 2026)

> **Method and trust.** Closes NF / UR cells in `observability_and_shift_left_vendors.md`; "Strong V" vendors were not redone. All 30 permitted searches were used. Page fetches were blocked (venturebeat.com, www.dbta.com failed; documentation hosts not retried), so documentation is quoted from search summaries. For primary evidence, vendor CLI/SDK packages were downloaded from PyPI and their source read. Tags: **[V-doc]** = package source read this session (shows what the API/CLI exposes, not that a feature is generally available); **[V-search]** = search summary only; **UR** only under Gaps.

## KQ1. What is analysed, at what granularity, and what does a developer see on the pull request?

### Takeaway
Datafold parses **warehouse query logs** (not the dbt manifest) with its own SQL compiler and anchors PR checks on that graph plus a data diff of a staging build. Foundational and Gable analyse **source code at rest**: Foundational posts native PR checks on every pending PR; Gable runs contract checks and code-to-field data-flow scans in CI. Monte Carlo, previously recorded as having no native PR check, now exposes a "PR Agent" with a lineage-weighted risk score and an experimental CI gate.

### Cited Findings

**Datafold**
- Docs FAQ "How is lineage computed?": by "ingesting, parsing and analyzing SQL logs from your databases and data warehouses", then augmenting the graph with metadata from orchestration tools (dbt named), BI tools and user documentation. The explorer shows the SQL behind a column and its read/write usage over the previous 7 days. [V-search, 2026-11-26] — [Datafold docs: Lineage](https://docs.datafold.com/data-explorer/lineage)
- Vendor blog (older, undated in the summary): the engine uses "a proprietary multi-dialect SQL compiler to analyze your data warehouses' query logs (as opposed to parsing your dbt project's manifest.json)", so it sees ad hoc tables outside dbt. [V-search] — [Datafold blog: What is Datafold Cloud](https://www.datafold.com/blog/what-is-datafold-cloud/)
- Refresh is scheduled: a cron setting controls when warehouse query history is scanned (SDK field `lineage_schedule`). Redshift needs syslog access. [V-search; V-doc datafold-sdk 0.5.0, 2026-10-27] — [Datafold docs: Redshift](https://docs.datafold.com/integrations/databases/redshift); [PyPI datafold-sdk](https://pypi.org/project/datafold-sdk/0.5.0/)
- PR behaviour: Datafold runs Data Diffs on modified dbt models (PR code built into a staging schema), "also identifies downstream assets (e.g., BI tools, reverse ETL pipelines) that might be impacted", and writes a summary as a PR comment linking to value-level differences. An AI Overview in the comment is available on GitHub, GitLab and Bitbucket. [V-search] — [Datafold docs: how CI works](https://docs.datafold.com/deployment-testing/how-it-works)
- Git providers: GitHub, GitLab, Bitbucket and Azure DevOps (comment posted on the PR; ADO/Bitbucket launched roughly January 2024). [V-search] — [Datafold docs: Azure DevOps](https://docs.datafold.com/integrations/code-repositories/azure-devops); [Datafold blog](https://www.datafold.com/blog/bitbucket-azure-devops-integrations-in-datafold/)
- Non-dbt repos use API-driven modes: the CLI has `datafold ci trigger` ("let Datafold work out the diffs from the pull request") alongside `datafold dbt upload --run-type production|pull_request`. [V-doc] — [PyPI datafold-sdk](https://pypi.org/project/datafold-sdk/0.5.0/)
- BI on the PR: affected Power BI assets are exposed "through Datafold's column-level lineage and automated impact analyses on pull requests". [V-search] — [Datafold blog: Power BI](https://datafold.com/blog/announcing-power-bi-integration)

**Foundational**
- "Lineage from code is read from the source itself", so it shows what a change touches before merge. [V-search, vendor docs] — [Foundational docs: assess impact before merging](https://docs.foundational.io/en/articles/14047433-assess-impact-before-merging-code-changes)
- Foundational CI: once a repository is configured, "every pending Pull Request is scanned" against end-to-end lineage for effects on downstream transformations, dashboards and ML models. Results are **native pull-request checks** with click-through detail; non-blocking by default, configurable to block merge. [V-search, vendor docs] — [Foundational docs: Foundational CI](https://docs.foundational.io/en/articles/9809341-continuously-check-your-pull-requests-with-foundational-ci)
- Dedicated extraction pages exist for Spark, Scala, Python, SQLAlchemy, Kafka and .NET; git hosts listed are GitHub, GitLab, Azure Repos, Bitbucket "and more". [V-search] — [Spark](https://docs.foundational.io/en/articles/9477498-foundational-spark-lineage); [SQLAlchemy](https://docs.foundational.io/en/articles/9805380-extracting-lineage-from-sqlalchemy); [Kafka](https://docs.foundational.io/en/articles/14771400-extracting-lineage-from-kafka); [.NET](https://docs.foundational.io/en/articles/14771402-extracting-lineage-from-net)

**Gable**
- `gable lineage scan`: "Scan a project for data lineage using static code analysis (SCA)". Languages `java` or `typescript`; the default backend is Java-only and takes a build command (for example `mvn clean install`) and Java version; TypeScript needs the "prime" backend. [V-doc, gable 0.75.3, 2026-10-27] — [PyPI gable](https://pypi.org/project/gable/0.75.3/)
- Output is field-level: data-flow paths from an ingress to an egress with a schema at each end, ordered code anchors, `ingress_field → egress_field` mappings, AI-generated transformation summaries, and a completeness flag (`UNKNOWN`, `KNOWN_INCOMPLETE`, `KNOWN_COMPLETE`) for each end, each schema and the field mappings. `gable lineage compare` diffs two scan results (added, removed, changed paths). [V-doc] — [PyPI gable](https://pypi.org/project/gable/0.75.3/)
- PR-time contract check: `gable data-asset check` offers `markdown` output "intended to be used as a PR comment"; enforcement levels are RECORD, NOTIFY, ALERT, BLOCK, INACTIVE, and the command fails when the highest violated level is BLOCK. [V-doc] — [PyPI gable](https://pypi.org/project/gable/0.75.3/)
- Not everything is pure static analysis. Database checks rely "on having a proxy database that mirrors your production database"; PySpark needs the job entrypoint and a Python executable "to be able to run the Pyspark script"; Kotlin needs a compiled jar. [V-doc] — [PyPI gable](https://pypi.org/project/gable/0.75.3/)
- Gable docs say "bundling and transmission of your code is necessary" for its static analysis, with fully in-CI analysis left to future releases; the vendor blog says a violating PR "generates a warning (or optionally a failure)". [V-search] — [Gable docs: CLI](https://docs.gable.ai/docs/prevention_and_alerting/cli); [Gable blog](https://www.gable.ai/blog/how-gable-implements-data-contracts---and-stops-bad-things-from-happening)

**Monte Carlo**
- Field lineage is query-derived: Redshift docs say query-log access lets Monte Carlo build table and field lineage; the API returns, per table, the "timestamp when the query that generated the lineage happened" and separately "other columns used in conditions". [V-search; V-doc pycarlo 0.15.715, 2026-11-26] — [MC docs: Redshift](https://docs.getmontecarlo.com/docs/redshift); [PyPI pycarlo](https://pypi.org/project/pycarlo/0.15.715/)
- Documented limits: Databricks table lineage "only available with Unity Catalog" (nodes expire after 7 days without update); "MC currently does not support lineage in Spark"; Sigma, Power BI dataflows and custom ETL connectors have no column-level lineage. [V-search] — [Databricks](https://docs.getmontecarlo.com/docs/overview-databricks); [Data lakes](https://docs.getmontecarlo.com/docs/data-lakes); [Sigma](https://docs.getmontecarlo.com/docs/sigma); [Custom ETL](https://docs.getmontecarlo.com/docs/custom-etl-integrations)
- **PR Agent (new).** It gives "a weighted risk assessment" of a PR's downstream effects and needs dbt project remote URLs to map a PR to monitored tables; GitLab (public preview) sends a merge-request impact report through a bot when dbt is integrated; Bitbucket (public preview) gets no PR comment. [V-search] — [MC docs: GitHub](https://docs.getmontecarlo.com/docs/github); [GitLab](https://docs.getmontecarlo.com/docs/gitlab); [Bitbucket](https://docs.getmontecarlo.com/docs/bitbucket)
- API detail: the agent reviews newly opened PRs or runs on an "mc review" comment; six risk weights (lineage blast radius, asset criticality, schema contract, code review, monitoring, historical signal); an experimental CI gate fails the CI step at a chosen risk tier (`low+`, `medium+`, `high+`, `none`); reviews beyond a monthly free allotment are billed. [V-doc, marked experimental] — [PyPI pycarlo](https://pypi.org/project/pycarlo/0.15.715/)
- RCA: only PRs merged after setup are collected; they are overlaid on volume and freshness charts (not schema-change monitors) and inspected by the Troubleshooting Agent. The API scores each PR's relevance to an incident and can name a PR "identified as root cause". [V-search; V-doc] — [MC docs: GitHub](https://docs.getmontecarlo.com/docs/github); [PyPI pycarlo](https://pypi.org/project/pycarlo/0.15.715/)

**Sifflet, Acceldata, Anomalo, Bigeye**
- Sifflet (vendor pages): agent "Sage correlates lineage, code changes, and metric drift"; dbt Impact Analysis surfaces impacted tables and dashboards in GitHub or GitLab, Bitbucket in progress. Lineage method not documented in what was seen. [V-search] — [Sifflet: lineage](https://siffletdata.com/product/data-lineage); [Sifflet: reclaim engineering capacity](https://siffletdata.com/solution-by-use-case/reclaim-engineering-capacity)
- Acceldata: docs describe column-level tracing for root cause and impact but not the derivation; one page derives Power BI–Redshift lineage by an "imprint-based asset inference process". No PR feature found. [V-search] — [Acceldata docs: Lineage](https://documentation.acceldata.io/p/8146/lineage)
- Anomalo: **table-level only**, for Databricks, Snowflake and BigQuery, read from the warehouse once a day; it "relies solely on database records", so Airflow steps are excluded. The API client offers only table-lineage edges. [V-search; V-doc anomalo 0.58.0, 2026-11-17] — [Anomalo: lineage](https://www.anomalo.com/automated-data-lineage-tools/); [PyPI anomalo](https://pypi.org/project/anomalo/0.58.0/)

**Paradime, Euno**
- Paradime: on PR open or push it "compares column-level lineage between the default branch and the PR branch", derives affected dbt nodes and downstream BI dashboards (Tableau, Looker, ThoughtSpot) and posts the summary in the PR. Needs a Turbo CI schedule; detects "structural column changes in SELECT statements". GitHub is native; GitLab and Azure DevOps call the Python SDK; Bitbucket has a setup page. [V-search] — [Paradime docs: lineage diff](https://docs.paradime.io/products/bolt/ci-cd/lineage-diff.md)
- The SDK confirms it: `LineageDiffClient.trigger_report(bolt_run_id, pull_request_number, user_email, changed_file_paths)` returns Markdown and JSON reports. [V-doc paradime-io 6.12.0, 2026-11-17] — [PyPI paradime-io](https://pypi.org/project/paradime-io/6.12.0/)
- Euno: integrations listed are Snowflake, BigQuery, Databricks, dbt, Fivetran, Tableau, Looker, Power BI; one secondary profile says impact analysis "can block changes in CI". Column method not found. [V-search, weak] — [YesPress profile](https://yespress.io/euno.md)

### Inferences
- Datafold anchors on the production graph plus a data diff, so it cannot see lineage that exists only in the PR; Foundational, Gable and Paradime re-analyse the changed code.
- Monte Carlo's PR Agent maps PRs through dbt projects, so it does not close the application-code gap.
- Gable's completeness flags are the only vendor-exposed admission seen that static lineage can be partial.

### Gaps
- Datafold: required (blocking) status not confirmed; only a "CI fails on primary key issues" setting was seen — [Datafold docs](https://docs.datafold.com/deployment_testing).
- Foundational: check content and false-positive rate; Java and dbt pages not surfaced.
- Monte Carlo: availability of PR Agent and CI gate; per-warehouse field-lineage matrix; Looker/Tableau field lineage.
- Sifflet and Acceldata column-lineage derivation: not found. Bigeye: not re-searched (budget); earlier notes stand.

## KQ2. Who reaches upstream of the warehouse, and what is documented as unsupported?

### Takeaway
Gable has the widest verifiable upstream surface (event schemas, application emitters, service-to-store flows). Foundational documents Kafka, .NET, Scala and SQLAlchemy extraction. Monte Carlo stops at Kafka Connect jobs on lineage edges and documents no Spark lineage.

### Cited Findings
- Gable source types: postgres, mysql, mssql, json_schema, avro, protobuf, python, pyspark, typescript, java, s3, dataframe, kotlin, swift, php, golang. Dedicated plugins cover the schema files, databases, Python, TypeScript and PySpark; Swift, Java, Kotlin, Go and PHP are registered through a generic "SCA Prime" plugin driven by annotations and rules files. [V-doc] — [PyPI gable](https://pypi.org/project/gable/0.75.3/)
- Gable's Python and TypeScript analysis targets event **emitter** functions (TypeScript presets: `segment`, `amplitude`, `brandviews`, `udf`). [V-doc] — [PyPI gable](https://pypi.org/project/gable/0.75.3/)
- Gable's graph: CODE components "populated only by static analysis scans"; DATA_STORE components authored by hand (`dynamodb | redis | elasticache | database | kafka | other`); cross-service edges; collection mechanism `SCA` or `BYOL`. No ORM names and no Open Data Contract Standard reference occur in the package. [V-doc] — [PyPI gable](https://pypi.org/project/gable/0.75.3/)
- Foundational IQ (2026-05-05): listed languages SQL, Python, Java, Scala, COBOL; the company says its engine "supports practically every coding language" (vendor claim). [V-search] — [BusinessWire](https://www.businesswire.com/news/home/20260505206817/en/Foundational-Launches-Foundational-IQ-Bringing-Deterministic-Code-Analysis-to-Agent-Deployment-for-Enterprise-Data-and-AI-Governance)
- Monte Carlo lineage-edge job types: Airflow, Azure Data Factory, Confluent / MSK / self-hosted Kafka Connect, Databricks, dbt, Fivetran, Dataform, Informatica, MuleSoft, Power BI dataflows, Salesforce Data Cloud, custom ETL. [V-doc] — [PyPI pycarlo](https://pypi.org/project/pycarlo/0.15.715/)

### Inferences
- In Gable, Kafka topics and other stores are declared nodes joined to scanned code, not discovered automatically.

### Gaps
- Whether Foundational's Kafka extraction reaches Avro/Protobuf fields, and Gable's ORM coverage: not found.

## KQ3. What quantified outcomes are published, and are any independent?

### Takeaway
Only Monte Carlo publishes named-customer resolution figures, all vendor-published. No independent measurement of pre-merge catch rates or lineage-attributable MTTD/MTTR reduction was found.

### Cited Findings
- T. Rowe Price (page updated 2025-12-17, vendor-published with customer permission): 83% lower time to resolution; people per issue from 5–6 to 2. — [Monte Carlo](https://montecarlo.ai/blog-how-t-rowe-price-reduced-time-to-resolution-83-with-monte-carlo/)
- Contentsquare (Feb 2023, vendor-published): 17% lower detection time and 16% lower resolution time in one month. — [Monte Carlo](https://montecarlodata.com/blog-how-contentsquare-reduced-time-to-data-incident-detection-by-17-percent-with-monte-carlo)
- Forrester Total Economic Impact (April 2025, **commissioned by Monte Carlo**, composite organisation): 358% ROI, USD 2.40M net present value. — [Forrester TEI](https://tei.forrester.com/go/montecarlo/dataaiobservabilityplatform)
- Monte Carlo's analysis of 1,000 troubleshooting investigations put code changes at roughly 10% of root causes; an earlier executive quote said about a third. Both vendor-sourced. — [Monte Carlo blog](https://www.montecarlodata.com/blog-has-ai-assisted-coding-made-data-quality-better-or-worse/); [Monte Carlo press post](https://montecarlo.ai/blog-monte-carlo-first-to-detect-breaking-code-changes-with-new-databricks-gitlab-integrations)
- Nearest academic source: Foidl et al. (2023) classified 600 GitHub issues from 11 projects by root cause; no detection or resolution times surfaced. — [arXiv 2309.07067](https://ar5iv.labs.arxiv.org/html/2309.07067)
- Practitioner posts carry no rates: a consultancy reports discovery moving "to Monday afternoon, before merge" on a 400-table Snowflake/dbt estate. — [Bacancy](https://www.bacancytechnology.com/insights/how-we-built-data-lineage-automation)

### Inferences
- If only about 10% of investigated incidents are code-caused, PR-time checks target a minority of incidents.

### Gaps
- Datafold, Foundational, Gable, Paradime, Sifflet, Acceldata, Anomalo, Euno outcome figures: not found.

## KQ4. What changed corporately in 2025–2026?

### Takeaway
Datafold, Foundational, Gable and Euno remain independent; Select Star and Secoda were absorbed by platforms; Monte Carlo repositioned around AI agents amid an unconfirmed layoff.

### Cited Findings
- **Monte Carlo**: repositioned as the "Agent Trust Platform" (post dated 2026-05-21) on montecarlo.ai; launched "Bayes" on 2026-10-29. Crowd-sourced trackers report a layoff of 80 people (29.6%) on 2026-03-17; **no company statement or press coverage was found**. — [Monte Carlo blog](https://montecarlo.ai/blog-new-era-monte-carlo); [HPCwire](https://www.hpcwire.com/bigdatawire/this-just-in/monte-carlo-launches-bayes-an-ai-teammate-that-fixes-production-ai-agents-and-their-data/); [Blind](https://www.teamblind.com/layoffs/company/monte-carlo-data); [TrueUp](https://trueup.io/co/monte-carlo)
- Monte Carlo pricing: credit wallet; Scale order form USD 0.25 per credit; AWS Marketplace 12-month "Monte Carlo Credit" dimension USD 50,000. — [Scale order form](https://www.montecarlodata.com/pricing/scale-order-form/); [AWS Marketplace](https://aws.amazon.com/marketplace/pp/prodview-hikicsfohm3gg)
- **Datafold**: independent; Migration Agent 2.0 (September 2025), Databricks Delivery Provider Program (April 2026), fixed-price "guaranteed-outcome" migrations; local MCP server replaced by a hosted one. Pricing quote-based; Vendr median USD 18,000 per year over 17 purchases (third party). — [Datafold blog](https://www.datafold.com/blog/the-datafold-migration-agent-2-0/); [Databricks programme](https://www.datafold.com/blog/datafold-joins-databricks-delivery-provider-program/); [PyPI datafold-sdk](https://pypi.org/project/datafold-sdk/0.5.0/); [Vendr](https://www.vendr.com/marketplace/datafold)
- **Foundational**: USD 8M seed announced 2024-03-25 is the only round found; no acquisition. — [BusinessWire](https://www.businesswire.com/news/home/20240325257775/en/Foundational-Secures-8M-to-Bring-AI-Agents-into-Data-Engineering)
- **Gable**: USD 20M Series A (2025) led by Crane Venture Partners, with Databricks Ventures and In-Q-Tel among backers; USD 27M total; no acquisition or 2026 round found. — [GeekWire](https://www.geekwire.com/2025/seattle-startup-gable-lands-20m-to-coordinate-data-changes-between-teams/)
- **Select Star**: Snowflake signed a definitive agreement for the "team and platform technology" (2025-11-24) to extend Horizon Catalog; terms undisclosed. — [Snowflake blog](https://snowflake.com/en/blog/snowflake-acquire-select-star/)
- **Secoda**: acquired by Atlassian on 2025-12-04; being folded into Rovo and the Teamwork Graph; "little will change for the time being". — [MarketScreener](https://www.marketscreener.com/news/atlassian-corporation-acquired-secoda-inc-ce7d51dfd181ff22); [Techzine](https://www.techzine.eu/news/analytics/137031/atlassian-acquires-secoda-to-expand-system-of-work)
- **Euno**: USD 23M Series A (2026-09-09) led by N47; USD 29M total; positioned as an "AI context platform". — [HPCwire](https://www.hpcwire.com/bigdatawire/this-just-in/euno-raises-23m-series-a-to-build-the-ai-context-brain-for-the-enterprise/)

### Gaps
- Whether the Snowflake–Select Star deal closed and whether the standalone product is still sold: not found. Secoda's lineage roadmap: not found.

## Summary table

| Vendor | Mechanism | PR-time impact | Incident RCA | Beyond-warehouse reach | Corporate status | Evidence |
|---|---|---|---|---|---|---|
| Datafold | Query-log parsing, own SQL compiler; dbt/BI enrichment; cron refresh | PR comment: data diff + downstream BI / reverse ETL; 4 git providers; blocking unconfirmed | Not found | BI, reverse ETL; no app code | Independent; migration-agent pivot | Medium (S + V-doc CLI) |
| Foundational | Static analysis of repo source | Native checks on every pending PR; optional blocking | Not found | Spark, Scala, Python, SQLAlchemy, Kafka, .NET (vendor docs) | Independent; USD 8M seed only | Medium (S, vendor docs) |
| Gable | Static analysis + schema files + proxy DB; field mappings with completeness flags | Contract check, Markdown comment, BLOCK level | Prevention only | Avro, Protobuf, JSON Schema, event emitters, Java/TS flows, five more languages by rules; stores declared | Independent; USD 27M raised | Strong for CLI (V-doc) |
| Monte Carlo | Query-log parsing; 10-day column TTL | PR Agent risk score; experimental CI gate; GitLab impact report | PR overlay, PR relevance score, Troubleshooting Agent | Kafka Connect jobs; no Spark lineage | "Agent Trust Platform"; layoff unconfirmed | Medium–strong (V-doc API + S) |
| Sifflet | Not found | dbt impact in GitHub/GitLab (vendor claim) | Sage agent (vendor claim) | Not found | Not found | Weak (S) |
| Acceldata | Not found | Not found | Lineage RCA described | Not found | Not found | Weak (S) |
| Anomalo | Warehouse-native, table-level, daily | Not found | Jump from alert to downstream tables | None | Not found | Medium (S + V-doc) |
| Bigeye | Earlier notes | Earlier notes | Earlier notes | Earlier notes | Not re-checked | Unchanged |
| Paradime | Column lineage diff, default vs PR branch (dbt) | PR report: dbt nodes + BI dashboards; 4 git providers | Not an incident tool | BI only | Not found | Medium (S + V-doc) |
| Euno | Not found | CI blocking (single secondary source) | Not found | BI semantic layers | Series A Sept 2026 | Weak |
| Select Star | Not found | Not found | Not found | Not found | Snowflake agreement Nov 2025; close unknown | Weak |
| Secoda | Not found | Not found | Not found | Not found | Atlassian since Dec 2025 | Weak |

## Still unresolved
1. Whether Datafold's check can block merge; content and accuracy of Foundational's checks.
2. Field-level lineage through Kafka with Avro/Protobuf (Foundational); ORM coverage (Gable).
3. Availability and price of Monte Carlo's PR Agent and CI gate; its per-warehouse field-lineage matrix; its March 2026 layoff (tracker-reported only).
4. Column-lineage derivation at Sifflet, Acceldata, Euno, Select Star, Secoda; fate of Select Star and Secoda as products.
5. Independent measurement of pre-merge catch rates or lineage-attributable MTTD/MTTR reduction: none found.
6. To close these: allow vendor documentation and news hosts in the session's network settings and re-run with a fresh search budget.
