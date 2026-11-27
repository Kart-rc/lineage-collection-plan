# Enterprise data lineage and governance vendors: element-level (column / field / attribute) lineage fact base, as of 26 November 2026

> **Method and reliability note (read first).**
> - Research date: 26 Nov 2026. Objectives referenced throughout: **O1** baseline lineage, **O2** incremental lineage, **O3** change impact analysis during code changes, **O4** incident detection and resolution.
> - **Page fetching was blocked in this session.** `www.ibm.com`, `productresources.collibra.com` and `www.solidatus.com` all failed DNS resolution from the sandbox (hosts outside the session's allowed network domains), so no vendor page could be opened in full. **Every finding below comes from web-search result summaries/snippets of the cited URL, not from a full read of the page.** Treat exact wording, version numbers and dates as "as surfaced by search" and re-verify anything load-bearing against the linked page.
> - **The shared web-search budget ran out** after roughly 56 queries. A final batch of eight queries did not run: Kafka/ML lineage for Atlan and IBM, data.world/ServiceNow lineage docs, Solidatus pricing and independent reviews, Precisely Data360 Govern status, Quest Smart Data Connector list, vendor MTTR case studies, and 2025-2026 corporate changes (Collibra, Alation, Atlan, Ataccama, Solidatus). Those topics are listed under Gaps and in the open questions at the end.
> - Labels used: **[doc]** vendor documentation, **[vendor]** vendor marketing/blog/press, **[3p]** third-party review, directory or aggregator (lower confidence, several are competitor-authored or SEO comparison sites), **[analyst]**, **[user]** user-submitted (ideas portal, forum). **(stale)** marks anything older than 2024.
> - Where a statement comes from my prior knowledge and was not sourced in this session, it is placed under Gaps and marked "unverified background".

---

## 1. IBM Manta (Manta Data Lineage / IBM watsonx.data intelligence "Data Lineage" / IBM Knowledge Catalog lineage)

### Takeaway
Manta is the deepest static-code-parsing lineage engine in this set: scanners parse SQL, stored procedures, ETL workflows, BI report definitions and COBOL/JCL into column-level lineage, and every scan produces a point-in-time **revision** (snapshot) that users can switch between. It is now sold as the "Data Lineage" capability of IBM watsonx.data intelligence, with OpenLineage import and export and a managed MCP server added in 2026; dynamic SQL, dbt/Airflow (OpenLineage-only), COBOL dynamic calls, CI/CD integration and pricing transparency are the documented or reported weak points.

### Cited Findings

**Product status and corporate**
- [vendor, 2026] IBM positions the capability as "Data Lineage (formerly IBM Manta Data Lineage)" inside IBM watsonx.data intelligence, providing automated data mapping "for both structured and unstructured data" — [IBM watsonx.data intelligence data lineage page](https://www.ibm.com/products/watsonx-data-intelligence/data-lineage); [IBM Manta product page](https://www.ibm.com/products/manta-data-lineage)
- [3p, 2026] Third-party review/comparison pages report that in 2026 `ibm.com/products/manta-data-lineage` redirects to the Data Lineage capability inside watsonx.data intelligence, that IBM acquired Manta in 2023, and that Manta lineage is "a separately licensed Manta service" rather than a native catalog feature — [DataTrail: IBM Manta alternative](https://datatrail.ai/alternatives/manta); [aiignitions Manta review](https://www.aiignitions.com/manta-review) (the search summary did not make clear which page carried which statement)
- [vendor, 2026] IBM states it is a Leader in the 2026 Gartner Magic Quadrant for Data and Analytics Governance Platforms — [IBM report landing page](https://www.ibm.com/forms/mkt-report-0d537)
- [analyst, secondhand, Q3 2025] A summary of the Forrester Wave: Data Governance Solutions Q3 2025 says IBM's governance offering is "integrated with tools like Manta for lineage" — [blog summary of the Forrester Wave](https://masterdatamanagementconcept.blogspot.com/2025/07/forrester-wave-data-governance.html)

**O1 baseline: collection mechanism and coverage**
- [vendor, 2026] Automated scanners are the core discovery method; they discover data flows in third-party tools such as Power BI, Tableau and Snowflake and extract technical lineage from databases, ETL and integration tools, scripts and reporting platforms — [IBM watsonx.data intelligence data lineage page](https://www.ibm.com/products/watsonx-data-intelligence/data-lineage)
- [3p, undated, possibly stale] A software directory lists "50+ out-of-the-box scanners" — [SourceForge Manta listing](https://sourceforge.net/software/product/Manta/). A current IBM scanner count was not found.
- [doc] IBM's support page on script counting lists the supported technologies and how each is counted, including OpenLineage, ER/Studio, Azure SQL Database and Microsoft SQL Server; per-technology pages enumerate stored procedures, triggers and functions as scanned objects — [IBM support: script counting details](https://www.ibm.com/support/pages/manta-automated-data-lineage-ibm-cloud-pak-data-script-counting-details)
- [vendor, undated] The Db2 scanner page describes parsing SQL logic to generate lineage "down to the column level" — [getmanta.com Db2 page](https://getmanta.com/technologies/databases/ibm-db2)
- [3p, 2026] Third-party reviews describe Manta as resolving lineage "by parsing the code itself, including SQL scripts and stored procedures", with scanners covering SQL, stored procedures, ETL workflows and BI report definitions, and as separating **direct** lineage from **indirect** lineage (filter and join conditions: elements that "influence" data versus elements that "carry" it) — [aiignitions Manta review](https://www.aiignitions.com/manta-review); [DBMS Tools: MANTA](https://dbmstools.com/tools/manta) (search summary did not make clear which of the two pages carried which sentence)
- [vendor] IBM states Manta "automatically extracts lineage from COBOL source code, IBM Db2 databases, JCL and other system components" — [IBM blog: The COBOL conundrum](https://www.ibm.com/new/product-blog/cobol-navigating-lineage-map)
- [doc] A SAS lineage connector is documented for watsonx.data intelligence — [IBM docs: SAS lineage](https://www.ibm.com/docs/en/DSXDOC/wsj/lineage/lineage-sas.html). A Databricks integration requirements page exists — [IBM Manta docs: Databricks](https://www.ibm.com/docs/en/manta-data-lineage?topic=databricks-integration-requirements)
- [doc, 2026] The "What's new" page lists a 26 June 2026 update adding lineage import from Microsoft Power BI Report Server among other sources — [IBM docs: What's new](https://www.ibm.com/docs/en/DSXDOC/wsj/getting-started/whats-new.html)
- [vendor, partner page, undated] Named scanners include Teradata, Informatica, Oracle and Microsoft SQL Server — [Teradata partner page for Manta](https://www.teradata.com/partners/manta). Release 38 (Nov 2022, **stale**) added Fivetran and Azure Data Factory scanners — [Engineering News, Nov 2022](https://www.engineeringnews.co.za/article/manta-enhances-data-lineage-platform-capabilities-with-release-38-2022-11-28)
- [vendor, 2026] "Custom Lineage Mappings" extend lineage beyond automated scanners with reusable lineage rules that "teach the platform how to interpret new technologies" — [IBM announcement: expanding OpenLineage support](https://www.ibm.com/new/announcements/turning-hidden-lineage-into-trust-expanding-openlineage-support-in-ibm-watsonx-data-intelligence)

**Documented limitations**
- [doc] "Most Automatic Data Lineage scanners don't support dynamic SQL queries out-of-the-box"; the Oracle scanner has a dynamic SQL processing feature for some patterns, and IBM documents converting dynamic SQL to static queries as a workaround — [IBM docs: How to handle dynamic SQL scripts](https://www.ibm.com/docs/en/manta-data-lineage?topic=articles-how-handle-dynamic-sql-scripts)
- [user, IBM Ideas portal] A customer reports that in their Manta DEV environment "~90% of COBOL programs are impacted" by unresolved dynamic calls, with manual mapping as the workaround; another reports the COBOL scanner failing with a parsing error on assembler code — [IBM Ideas DATALIN-I-179](https://ibm-data-and-ai.ideas.ibm.com/ideas/DATALIN-I-179) (search summary attributed these to ideas-portal posts; exact idea IDs not confirmed)
- [3p, approx. Sept 2026] An independent review lists cons: dated UI, **no dedicated dbt or Airflow scanners** (both arrive only as OpenLineage events), and a heavy footprint of "12+ cores, 64-256 GB RAM, 1 TB metadata storage" — [Data Stack Index: IBM Manta review](https://datastackindex.com/data-observability/tools/ibm-manta/)
- [user, Jan-Feb 2026] Ideas-portal entries state that Manta "currently does not parse" the transformation fields of the OpenLineage column-level facet, that column-level lineage ingested through OpenLineage is not preserved when exporting to Alation, and that column export misbehaves for Virtual File System sources — [DATALIN-I-210](https://ibm-data-and-ai.ideas.ibm.com/ideas/DATALIN-I-210); [DATALIN-I-214](https://ibm-data-and-ai.ideas.ibm.com/ideas/DATALIN-I-214); [DATALIN-I-261](https://ibm-data-and-ai.ideas.ibm.com/ideas/DATALIN-I-261) (feature requests; current status unknown)

**OpenLineage, APIs and export**
- [doc] OpenLineage events are imported and correlated with scanner-collected lineage; column lineage comes through only when the column-lineage facet is present — [IBM docs: OpenLineage integration](https://www.ibm.com/docs/en/DSXDOC/wsj/lineage/openlineage-integration.html)
- [vendor, 2026] Lineage can also be **exported** in OpenLineage format, including at column level, so the product supports both import and export — [IBM announcement: OpenLineage export](https://www.ibm.com/new/announcements/openlineage-export-in-ibm-watsonx-data-intelligence-expands-interoperability)
- [vendor/doc, Mar 2026] Technical lineage can be exported to Collibra at table level, column level or both — [IBM community post, 25 Mar 2026](https://community.ibm.com/community/user/blogs/diana-toma/2026/03/25/technical-data-lineage-export-to-collibra); [IBM docs: exporting lineage to Collibra](https://www.ibm.com/docs/en/DSXDOC/wsj/lineage/lineage-export-collibra.html). Export to Alation existed as of Manta 42.9 — [IBM Ideas DATALIN-I-74](https://ibm-data-and-ai.ideas.ibm.com/ideas/DATALIN-I-74). A data.world integration page exists — [manta.io data.world integration](https://manta.io/integrations/data.world)

**O2 incremental: revisions and scan types**
- [doc] Each **revision** is a point-in-time snapshot of metadata and lineage; "users will see the most recent revision by default but can switch to an older revision showing the metadata and lineage at an earlier point in time" — [IBM docs: Understanding revisions](https://www.ibm.com/docs/en/manta-data-lineage?topic=documentation-understanding-revisions)
- [doc] IBM recommends the **Targeted scan**, on by default for new installations from R42.5; legacy scans are deprecated. Targeted scans cover only the selected connections, **start from the last revision**, and remove deprecated objects; legacy major-revision scans rescan everything starting from an empty revision — [IBM docs: Understanding revisions for administrators](https://www.ibm.com/docs/en/manta-data-lineage?topic=concepts-understanding-revisions-administrators)
- [vendor] The product page advertises column-level **historical lineage** with filtering and colour-coding — [IBM Manta product page](https://www.ibm.com/products/manta-data-lineage)
- [3p partner, undated] A reseller page says two revisions can be selected to see added and removed elements ("time-slicing") — [Masterdata: MANTA revisions](https://www.masterdata.co.za/index.php/enhance-dataops-with-mantas-time-slicing-feature); **contradicted by** a competitor page listing "Lineage diff (not supported)" — [DataTrail](https://datatrail.ai/alternatives/manta). Not confirmed in IBM documentation.
- [academic] A Charles University thesis on MANTA Flow describes an algorithm that re-analyses only changed files plus the few unchanged ones whose lineage could differ — [Precise and Efficient Incremental Update of Data Lineage Graph](https://dspace.cuni.cz/handle/20.500.11956/173511). This is research, not confirmation of shipped behaviour.
- [vendor-adjacent] A Neo4j customer story says Manta lets users "conduct introspective queries about past changes" in addition to showing the current map — [Neo4j customer story: IBM Manta](https://neo4j.com/customer-stories/ibm-manta-data-lineage/)

**O3 / O4 and AI**
- [vendor, Apr 2026] IBM announced a **managed MCP server** exposing governed data-intelligence capabilities to external AI agents and a Data Intelligence Chat Agent embedded in the UI; the product page describes natural language, MCP and reusable Agent Skills — [IBM community post, 23 Apr 2026](https://community.ibm.com/community/user/blogs/diana-toma/2026/04/23/ibm-introduces-agentic-data-intelligence); [watsonx.data intelligence product page](https://www.ibm.com/products/watsonx-data-intelligence)
- [vendor] OpenLineage export is positioned as showing "how changes or data issues propagate across datasets" for external observability platforms — [IBM announcement: OpenLineage export](https://www.ibm.com/new/announcements/openlineage-export-in-ibm-watsonx-data-intelligence-expands-interoperability)

**Pricing and deployment**
- [vendor] AWS Marketplace listing: custom pricing only, contact IBM sales — [AWS Marketplace: IBM Manta Data Lineage](https://aws.amazon.com/marketplace/pp/prodview-4lt7554c34ecs)
- [doc] The Cloud Pak for Data edition is sold in Resource Units, where one RU is 30,000 scripts — [IBM support note](https://www.ibm.com/support/pages/node/6569497). For watsonx.data intelligence, one resource unit equals one data source definition or 5,000 database tables — [IBM docs: service plans](https://www.ibm.com/docs/en/DSXDOC/wsj/getting-started/wkc-plans.html)
- [reseller] CDW Canada lists a subscription licence for one resource unit of "MANTA Automated Data Lineage for IBM Cloud Pak for Data" at CAD 139,632.99 — [CDW.ca listing](https://cdw.ca/product/manta-automated-data-lineage-for-ibm-cloud-pak-for-data-subscription-lice/8162737)
- [3p, low confidence] Software Advice shows "starting at $30,000 per year"; G2 says no pricing provided (last updated June 2023, **stale**) — [Software Advice](https://www.softwareadvice.com/master-data-management/manta-flow-profile/); [G2](https://g2.com/products/manta-flow/pricing)

### Inferences
- Mechanism class: **static code and metadata parsing** (scanner per technology) with OpenLineage as a runtime supplement. This is the pattern best suited to stored-procedure-heavy and mainframe estates and least suited to code generated at runtime.
- O2 is genuinely incremental at the *connection* level (Targeted scans start from the previous revision), and history is first-class (revisions). Whether file-level delta analysis ships, and whether a two-revision diff exists in the current IBM-branded product, are unresolved.
- For the buyer's estate (microservices -> Kafka/Flink -> warehouse -> feature store -> ML), Manta would cover the warehouse/SQL leg natively and depend on OpenLineage import or Custom Lineage Mappings for microservices, streaming and feature-store hops. The reported OpenLineage column-facet gap (transformation fields not parsed, Jan 2026) matters for exactly those hops.
- No CI/CD or pull-request integration was found; O3 appears to be interactive impact analysis plus agent/MCP access.
- The Neo4j customer story implies a Neo4j graph store underneath Manta; resource requirements (64-256 GB RAM) are consistent with a heavyweight self-managed deployment.

### Gaps
- Current IBM scanner count and the definitive scanner list (Java, Python, Spark, Kafka, Talend, SSIS, DataStage, PowerCenter individually) were not retrievable; `getmanta.com/technologies` and IBM docs could not be opened.
- Kafka/streaming and ML model/feature lineage support in Manta: **not found** (search budget exhausted before the query ran).
- Scan scheduling mechanics and typical scan latency: not found in IBM docs (one competitor page says "whatever cadence the site chooses").
- Any published MTTD/MTTR or productivity figure for Manta: not found.
- Whether "unstructured data lineage" is scanner-based or OpenLineage-based: not found.
- Unverified background: Manta acquisition by IBM closed October 2023 (one third-party page gives only "2023").

---

## 2. Collibra (Collibra Data Lineage, formerly SQLDep; technical lineage via Edge)

### Takeaway
Collibra builds technical lineage by parsing SQL and tool metadata collected through Edge (the CLI lineage harvester reached end of life on 31 July 2026), supplemented by OpenLineage (Airflow, AWS Glue/Spark, dbt) and by reading platform lineage tables (Databricks Unity Catalog, Google Dataplex). Column-level support is real but source-by-source, with documented exclusions for dynamic SQL, cursors, encrypted definitions, Redshift stored procedures, Glue DynamicFrames and Power BI DirectQuery; 2026 additions are lineage read APIs and an MCP server rather than CI/CD checks or lineage versioning.

### Cited Findings

**O1 baseline: mechanism and coverage**
- [doc, 2026.08] "The CLI lineage harvester reached its end of life on July 31, 2026" and new versions are no longer released; Collibra recommends creating technical lineage via Edge — [Collibra docs 2026.08: supported data sources for technical lineage](https://productresources.collibra.com/docs/collibra/2026.08/Content/CollibraDataLineage/ref_technical-lineage-supported-data-sources.htm)
- [doc, 2026.02] Supported sources include Azure SQL Data Warehouse, Databricks Unity Catalog, Google Dataplex, Greenplum, Amazon Redshift, IBM Db2 and SAP HANA among others; support depends on version and connection type (JDBC, folder, shared storage) — [Collibra docs 2026.02: supported data sources](https://productresources.collibra.com/docs/collibra/2026.02/Content/CollibraDataLineage/TechnicalLineage/ref_technical-lineage-supported-data-sources.htm)
- [doc] Stored-procedure support varies: Oracle lists "SQL based input and stored procedures"; for Amazon Redshift "stored procedures are not supported"; lineage cannot be created for views and procedures whose SQL definitions are encrypted in the database — [Collibra docs 2024.10: supported data sources](https://productresources.collibra.com/docs/collibra/2024.10/Content/CollibraDataLineage/TechnicalLineage/ref_technical-lineage-supported-data-sources.htm)
- [doc] With a JDBC connection, column-level lineage is not generated for tables created by SQL statements (CREATE TABLE AS SELECT) unless the SQL is supplied through a shared-storage or folder connection — [Collibra docs 2024.10](https://productresources.collibra.com/docs/collibra/2024.10/Content/CollibraDataLineage/TechnicalLineage/ref_technical-lineage-supported-data-sources.htm)
- [doc] Databricks Unity Catalog column lineage is extracted from the `system.access.column_lineage` table; for Google Dataplex the user chooses table-level or column-level, and column-level needs a Google export API that is in Preview. Both are built through the "custom technical lineage" scanner and appear as CUSTOM-LINEAGE sources — [Collibra docs: create technical lineage via Edge](https://docs.collibra.com/Content/CollibraDataLineage/TechnicalLineage/TechnicalLineageviaEdge/to_tech-lin-edge-workflow.htm)
- [doc] Supported SQL syntax page: **cursors and dynamic queries are unsupported**, dynamic SQL "yields limited results"; the documented workaround is to log dynamic SQL at runtime so it becomes a static query — [Collibra docs: supported SQL syntax](https://productresources.collibra.com/docs/collibra/latest/Content/CollibraDataLineage/ref_supported-sql-syntax.htm)
- [doc] **OpenLineage ingestion**: technical lineage for Airflow uses the OpenLineage Airflow integration and for AWS Glue the OpenLineage Spark integration. Airflow column-level lineage is limited to specific operator classes; for Glue it covers only Spark SQL DataFrames because "the OpenLineage Spark plugin cannot extract data lineage from AWS Glue Spark Jobs that use AWS Glue DynamicFrames". dbt is supported for listed adapters — [Collibra docs: OpenLineage supported transformations](https://productresources.collibra.com/docs/collibra/latest/Content/CollibraDataLineage/DataSources/OpenLineage/ref_openlineage-supported-transformations.htm); [Airflow supported transformations](https://productresources.collibra.com/docs/collibra/latest/Content/CollibraDataLineage/DataSources/ApacheAirflow/ref_airflow-supported-transformations.htm)
- [doc] ETL/BI: IBM InfoSphere DataStage lineage is created on Edge (2026.02); Tableau and MicroStrategy lineage on Edge (2024.10); Looker through its API; Power BI lineage **excludes DirectQuery and live connections**; the MicroStrategy and Power BI lineage *harvesters* are labelled deprecated (2026.02); some BI lineage is created automatically but **stitching is not available** — [Collibra docs 2026.02](https://productresources.collibra.com/docs/collibra/2026.02/Content/CollibraDataLineage/TechnicalLineage/ref_technical-lineage-supported-data-sources.htm); [Collibra docs 2024.10](https://productresources.collibra.com/docs/collibra/2024.10/Content/CollibraDataLineage/TechnicalLineage/ref_technical-lineage-supported-data-sources.htm)
- [3p, unverified against Collibra docs] A competitor page says Collibra supports Informatica PowerCenter, SSIS and DataStage, plus Tableau, Power BI (import mode), Looker, MicroStrategy and SSRS, and quotes a restriction that technical lineage via Edge "can only access Redshift and Snowflake projects" — [DataTrail: Collibra Data Lineage](https://datatrail.ai/collibra-data-lineage)
- [3p] A review states technical lineage is documented as a cloud-only product — [datacatalog.net Collibra review](https://datacatalog.net/collibra-review/)
- [3p, attribution uncertain] A consultancy blog says Collibra needs specialised scanners (IBM Manta, Solidatus) for legacy environments such as SAP ABAP, custom ETL and proprietary BI — [Murdio: data lineage standards](https://murdio.com/insights/insights-data-lineage-standards/)
- [doc, 2026] Release notes list a "Streaming API lineage flow" for technical lineage for GCP as generally available on 8 November 2026 — [Collibra release 2026.06 notes](https://productresources.collibra.com/docs/collibra/latest/Content/ReleaseNotes/Archive/ref_release-202606.htm) (as surfaced by search; the release/date pairing looks odd and should be re-checked)
- [vendor, Mar 2026] IBM documents a supported path to push Manta technical lineage into Collibra at table and/or column level — [IBM community post](https://community.ibm.com/community/user/blogs/diana-toma/2026/03/25/technical-data-lineage-export-to-collibra)

**O3 / AI: lineage APIs and MCP**
- [vendor, 2026] Collibra published "Data lineage read APIs, MCP server: lineage on demand": lineage is exposed as callable tools to any MCP-compatible agent, positioned for tracing impact and provenance "before changes ship, not after something breaks" — [Collibra blog](https://www.collibra.com/blog/data-lineage-read-apis-mcp-server-lineage-on-demand)
- [vendor] MCP server product page: "Trace upstream sources and downstream dependencies in one query. Get impact analysis before a change ships"; read and write operations within the existing permissions model; requires an OAuth 2.0 application — [Collibra MCP server](https://www.collibra.com/products/mcp-server); tool reference — [Collibra docs: MCP tools](https://productresources.collibra.com/docs/collibra/latest/Content/ModelContextProtocol/ref_mcp-tools.htm)
- [doc, Nov 2026] Release 2026.11 adds an MCP Server asset type and lets the AI Agent asset type call MCP tools (needs MCP governance enabled in AI Command Center) — [Collibra release 2026.11 notes](https://productresources.collibra.com/docs/collibra/latest/Content/ReleaseNotes/Archive/ref_release-202611.htm). AI Command Center launched May 2026 — [BigDATAwire/HPCwire](https://www.hpcwire.com/bigdatawire/this-just-in/collibra-launches-ai-command-center-to-scale-agentic-ai-with-real-time-oversight-and-continuous-control). The MCP server is listed in the Databricks Marketplace — [Collibra blog](https://www.collibra.com/blog/trusted-agents-at-scale-collibra-launches-mcp-server-in-the-databricks-marketplace-to-power)

**Pricing and analyst position**
- [3p] Vendr buyer guide: average contract about USD 166,000/yr from 5 deals, range about USD 129,000-189,000 — [Vendr buyer guide](https://vendr.com/buyer-guides/collibra). CostBench cites a Vendr median of USD 197,142 (n=6, "limited data") and a 12-month Cloud Platform plan at about USD 170K/yr, with hidden costs adding 20-30% — [CostBench](https://www.costbench.com/software/data-catalog/collibra/). Collibra publishes no list price; one benchmark site claims 28-55% enterprise discounts and three-year terms and notes the lineage module "can escalate materially with data estate growth" (no figure) — [VendorBenchmark](https://vendorbenchmark.com/vendors/collibra-pricing)
- [vendor] Leader in the 2026 Gartner MQ for Data and Analytics Governance Platforms "for the third year in a row" — [Collibra resource page](https://www.collibra.com/resources/2026-gartner-magic-quadrant-for-data-analytics-platforms). Champion in Bloor's 2024 Market Update for Data Governance (Nov 2024) — [Collibra press release](https://www.collibra.com/company/newsroom/press-releases/collibra-has-been-continually-recognized-in-data-and-ai-governance-by-industry-analysts-in-2024)

### Inferences
- Mechanism class: **SQL/code parsing in Collibra's cloud lineage service fed by Edge**, plus **OpenLineage ingestion** and **system-table reads**. Coverage is a patchwork, so the per-source matrix needs to be validated against the buyer's exact estate.
- "Stitching is not available" for some auto-created BI lineage is a material caveat for end-to-end column-level claims; cross-system identity matching presumably relies on full-name matching of database/schema/table/column, which is why stitching failures occur (not confirmed in sources).
- O2: nothing surfaced on incremental sync, lineage history, time travel or diff. Absence in search results is not proof of absence, but two competitor matrices and Collibra's own pages surfaced no such feature.
- O3: "impact analysis before a change ships" is delivered through an agent/MCP call, not a documented GitHub/GitLab check.
- Collibra customers commonly import deeper lineage from Manta (IBM documents the export), which suggests Collibra's native scanners are not considered sufficient for legacy/mainframe estates.

### Gaps
- Full list of supported ETL/BI sources in 2026.x (PowerCenter, SSIS, Talend, SSRS) could not be confirmed from Collibra's own docs (host blocked).
- Sync behaviour (full vs incremental), scheduling and latency: not found.
- Lineage versioning/history/diff: not found.
- Kafka/streaming and AI-model lineage: not found (query did not run).
- AWS Marketplace list price and a separate lineage SKU price: not found.
- Exact names/parameters of the lineage MCP tools and whether they return column-level results: not found.
- Unverified background: Collibra Data Lineage originates from the 2019 SQLdep acquisition; Collibra made further acquisitions in 2025 (not verified this session).

---

## 3. Informatica (IDMC Cloud Data Governance and Catalog, CLAIRE, EDC scanners; now part of Salesforce)

### Takeaway
Informatica CDGC harvests lineage through catalog-source scanners run from Metadata Command Center (PowerCenter, IDMC/CDI mappings, RDBMS, SQL and stored-procedure scripts, BI), with column-to-column lineage and transformation logic strongest for Informatica's own ETL. Salesforce completed its acquisition on 18 November 2025; 2026 activity is concentrated on CLAIRE agents and "headless" MCP servers. Third-party evidence says historical lineage and lineage diff are not supported, and no CI/CD integration was found.

### Cited Findings

**Corporate**
- [press, 18 Nov 2025] Salesforce completed its acquisition of Informatica — [Salesforce press release](https://www.salesforce.com/news/press-releases/2025/11/18/salesforce-completes-acquisition-of-informatica/). Deal reported at about USD 8bn — [TechRadar](https://www.techradar.com/pro/salesforce-snaps-up-informatica-in-usd8bn-deal-to-boost-ai-tools)
- [vendor] Salesforce said it would rapidly integrate Informatica's technology stack, including data integration, quality, governance and unified metadata for Agentforce — [Salesforce press release](https://www.salesforce.com/news/press-releases/2025/11/18/salesforce-completes-acquisition-of-informatica/); a Salesforce page says Informatica's governance tools will be integrated across the platform, enhancing Data 360, Agentforce 360 and MuleSoft — [Salesforce Informatica page](https://www.salesforce.com/informatica/?bc=OTH)
- [vendor] Informatica states it is a Leader in the Gartner MQ for Data and Analytics Governance Platforms (dated 6 January 2026) — [Informatica MQ page](https://www.informatica.com/data-governance-magic-quadrant.html)

**O1 baseline**
- [vendor, data sheet] CDGC provides "complete column-level data lineage", parsing of SQL scripts and stored procedures, the ability to "inspect scripts, procedures and processes to fully understand logic and internal data flow", detailed upstream/downstream impact analysis, and a custom metadata framework to ingest lineage from spreadsheet files for sources without a scanner — [Informatica CDGC data sheet](https://www.informatica.com/gb/resources/data-sheets/cloud-data-governance-and-catalog-with-informatica.html)
- [vendor, data sheet] CDGC can "scan static and dynamic code and perform language parsing for automated data lineage" (marketing; object coverage not specified) — [CDGC data sheet PDF](https://www.informatica.com/content/dam/informatica-com/en/collateral/data-sheet/cloud-data-governance-and-catalog_data-sheet_4152en.pdf)
- [vendor enablement deck] Lineage categories: *technical automated lineage* covers table-to-table and column-to-column flows from CDI/IICS, PowerCenter and RDBMS scans; *linked-catalog inferred lineage* applies to relational databases and file-system sources (S3, ADLS) — [Informatica Tech Tuesdays: Data Lineage in CDGC, Part 1](https://www.informatica.com/content/dam/informatica-cxp/techtuesdays-slides-pdf/Data%20Lineage%20in%20CDGC%20A%20Practical%20Guide%20to%20Key%20Categories%20and%20Setup%20Approaches%20-%20Part%201.pdf)
- [practitioner] PowerCenter is scanned as a catalog source pulling workflow and repository metadata; PowerCenter parameter files must be copied to the Secure Agent machine for lineage to resolve — [Medium: Configure PowerCenter resource in CDGC](https://medium.com/@kapildev.pund/configure-powercenter-resource-in-iics-cdgc-2879f55b1ca3)
- [vendor, Oct 2026] The October 2026 release lists Databricks Unity Catalog foreign catalogs and Databricks Unity Catalog stored procedures as newly covered — [What's New in CDGC, October 2026 release](https://success.informatica.com/content/dam/informatica-cxp/techtuesdays-slides-pdf/Whats%20New%20in%20Informatica%20CDGC,%20CDMP,%20CDAM%20and%20CDQ%20in%20October%202026%20Release.pdf)
- [vendor KB] The CDGC runbook lists supported scanners including Informatica PowerCenter, Databricks and Db2 AS/400; script catalog sources exist for Teradata BTEQ and Azure SQL Server scripts — [CDGC Runbook](https://knowledge.informatica.com/s/article/CDGC-Runbook?language=en_US)
- [3p, 2026] An independent review counts 99 documented source types, including SAP BW, Teradata scripts and mainframe JCL — [Data Stack Index: Informatica CDGC review](https://datastackindex.com/data-observability/tools/informatica-cdgc/)
- [doc, legacy] "Advanced Scanners" is the term used in Enterprise Data Catalog 10.4/10.5 documentation (on-prem predecessor) — [Informatica docs: EDC Advanced Scanners (10.5)](https://docs.informatica.com/data-security-group/test-data-management/10-5/what-s-new-and-changed/part-1--version-10-5/10-5-what-s-new/enterprise-data-catalog/advanced-scanners.html)

**O2 incremental**
- [3p, 2026] The same independent review lists "Historical lineage (not supported)" and "Lineage diff (not supported)" for CDGC — [Data Stack Index](https://datastackindex.com/data-observability/tools/informatica-cdgc/)
- [vendor] An April 2026 emergency bug fix addressed a lineage export failure — [Informatica Pulse release note](https://pulse.informatica.com/releases/R-01652?tab=Upcoming)

**O3 / O4 and AI**
- [press, May 2025] The original CLAIRE Agents suite included a **Data Lineage Agent** that "automatically generates granular data lineage across diverse coding environments" — [Nasdaq: Informatica unveils agentic AI offerings](https://www.nasdaq.com/press-release/informatica-unveils-agentic-ai-offerings-its-ai-powered-cloud-data-management). CLAIRE Agents can act as an A2A endpoint and as both MCP client and server — [InfoWorld](https://www.infoworld.com/article/3985378/informatica-adds-agents-to-automate-its-intelligent-data-management-cloud.html)
- [press, 20 May 2026] "Headless data management": Informatica MCP servers and CLAIRE agent skills extended to AWS AI services (AWS Agent Registry, Amazon Quick); MCP servers on Quick GA in US regions, agent skills in preview — [Salesforce/Informatica press release](https://www.salesforce.com/news/press-releases/2026/05/20/informatica-announces-headless-data-management-aws/). Extended to Google Cloud, Snowflake and Databricks — [CX Today](https://www.cxtoday.com/crm/informatica-from-salesforce-goes-headless-across-google-cloud-snowflake-and-databricks/)
- [doc, Jul 2026] A Catalog Discovery MCP server for CDGC lets AI agents discover and explore catalog assets; an IPU Management MCP server exports IPU usage — [Informatica MCP what's new](https://onlinehelp.informatica.com/IICS/prod/agentic-ui/en/aa-aiae-mcp-whats-new/New_features_and_enhancements_2.html)
- [analyst, vendor-sponsored, Sep 2026] A Futurum paper describes a lineage engine attaching an end-to-end lineage graph to agent output for auditing — [Futurum: Elevate AI Agent Quality](https://futurumgroup.com/wp-content/uploads/2026/09/Elevate-AI-Agent-Quality-with-Active-Intelligent-Context.pdf)
- [vendor-commissioned] Forrester TEI of IDMC says engineers "gain improved visibility into data lineage, system dependencies, and data flows, making it easier to ... troubleshoot issues"; no quantified root-cause figure surfaced — [Forrester TEI of Informatica IDMC](https://tei.forrester.com/go/informatica/IDMC/index.html?lang=en-us)

**Legacy product status**
- [vendor KB] Informatica has published an End of Support announcement for Enterprise Data Catalog, Enterprise Data Preparation and Data Privacy Management versions 10.4.1 and earlier — [Informatica KB DOC-16182](https://knowledge.informatica.com/s/article/DOC-16182?language=en_US)
- [user, Oct 2026] A community post reports lineage diagrams loading very slowly in EDC 10.5.2 after a PowerCenter scan — [Informatica Network: EDC topic](https://network.informatica.com/s/topic/0TO6S000000JA9eWAG/enterprise-data-catalog)

### Inferences
- Mechanism class: **scanner-based metadata and code extraction** (Secure Agent runs scanners; lineage assembled in CDGC), strongest where the transformation engine is Informatica's own, because the mapping metadata already carries field-level expressions.
- Cross-system stitching relies on linking catalog sources ("linked-catalog inferred lineage") and on resolving connection parameters, which is why missing PowerCenter parameter files break lineage.
- O2 looks weak: rescans on a schedule, no surfaced history or diff. O3 is interactive impact analysis plus agent access; no pull-request check.
- Strategic risk: roadmap now sits inside Salesforce, with emphasis on Agentforce/Data 360 context; neutrality toward non-Salesforce estates is an open question rather than an evidenced problem.

### Gaps
- Definitive CDGC scanner list and whether PL/SQL, T-SQL, COBOL, Kafka, Spark/Python are covered at column level: not confirmed from Informatica documentation.
- Incremental metadata extraction / change detection behaviour: not found.
- IPU price points and AWS Marketplace pricing for CDGC: not found.
- End-of-support date for EDC 10.5.x and the EDC-to-CDGC migration path: not found.
- Published MTTR/productivity figures tied to lineage: not found.
- The phrase "lineage reaches the column and shows the transformation logic" surfaced in a search summary of 2026 material but could not be attributed to a specific page.

---

## 4. Solidatus

### Takeaway
Solidatus is a lineage *modelling* platform: connectors and an OpenLineage ingester populate a governed, **bi-temporally versioned** lineage model that also supports what-if scenarios, which makes its O2 history story the strongest on paper. Evidence is almost entirely vendor-authored; 2026 releases added an AI Lineage Assistant (March) and MCP support with bring-your-own-LLM (2026.3).

### Cited Findings
- [vendor] Connectors "capture column-level lineage and parse stored procedures" so a problem can be traced to a specific field — [Solidatus connectors page](https://www.solidatus.com/features/connectors/)
- [vendor] The **OpenLineage connector** ingests column-level lineage from any platform that publishes OpenLineage events (support most mature for Apache Spark); repeated job runs are consolidated into one versioned model; events lacking column-level detail are flagged — [Solidatus OpenLineage page](https://www.solidatus.com/product/openlineage/)
- [3p profile] Metadata sources listed: Snowflake, Databricks, Azure, AWS, Oracle, SQL Server, Informatica, dbt, mainframes and analytics tools; versioning described as **bi-temporal** (when something was true in the business versus when it was recorded) — [Yespress profile of Solidatus](https://yespress.io/solidatus)
- [vendor] The site describes viewing how data looked in the past, tracking how issues were resolved and modelling what-if scenarios — [Solidatus home page](https://solidatus.com/)
- [press, 10 Mar 2026] AI Lineage Assistant launched: drafts mappings, proposes connections and converts PDFs and spreadsheets into structured models — [Solidatus press release](https://www.solidatus.com/news/solidatus-launches-ai-lineage-assistant/); [IT Brief](https://itbrief.com.au/story/solidatus-unveils-ai-assistant-to-automate-data-lineage)
- [press, 2026] Release 2026.3 adds **MCP support** (external AI tools and agents can connect and work with lineage model content), a Bring Your Own LLM option, and AI Assistant updates including persistent sessions and workflow tools — [IT Brief](https://itbrief.news/story/solidatus-adds-ai-governance-tools-to-lineage-platform); [A-Team Insight](https://a-teaminsight.com/blog/solidatus-updates-ai-to-give-agentic-boost-to-workflow-speed-and-scale/?brand=ati); [Solidatus blog on 2026.3](https://www.solidatus.com/blog/solidatus-2026-3-puts-data-lineage-where-ai-agents-can-reach-it/)
- [3p] The Yespress headline cites a "$247,500" figure in connection with Solidatus; the snippet does not say what it covers, so it is not usable as a price point — [Yespress](https://yespress.io/solidatus)

### Inferences
- Mechanism class: **connector-harvested metadata plus manual/AI-assisted modelling**, with OpenLineage as the runtime feed. The AI assistant converting PDFs and spreadsheets into models indicates that a meaningful share of Solidatus lineage is curated rather than parsed.
- O2: versioned model with bi-temporal history and run consolidation is the clearest "time travel" design among the vendors; whether it applies at column granularity and supports automated diff between two versions was not confirmed.
- O3: what-if modelling exists as a planning feature; no CI/CD or pull-request integration surfaced.
- Fit: regulatory lineage in financial services (BCBS 239-style) rather than engineering-led change management.

### Gaps
- Complete connector list, column-level coverage per source, stored-procedure dialects: not found.
- Kafka/streaming, microservices and ML lineage: not found.
- Pricing, deployment options and AWS Marketplace listing: not found (query did not run).
- Independent analyst or practitioner reviews (Bloor, G2, Reddit): not found.
- MTTD/MTTR figures: not found.

---

## 5. Cloudera Octopai (now "Cloudera Data Lineage")

### Takeaway
Octopai, acquired by Cloudera (announced 14 November 2024), extracts metadata with scheduled extractors and analyses it centrally to produce three lineage layers: cross-system, inner-system and end-to-end column lineage, across 60+ technologies with particular depth in legacy ETL and BI. Release notes through June 2026 show rapid connector expansion (Hive, Impala, NiFi, Trino, Fabric, dbt Cloud, Databricks), but streaming was explicitly unsupported in mid-2025 and no lineage diff or CI/CD integration was found.

### Cited Findings
- [press, 14 Nov 2024] Cloudera announced the acquisition of Octopai's platform — [Cloudera press release](https://www.cloudera.com/about/news-and-blogs/press-releases/2024-11-14-cloudera-to-acquire-octopais-platform.html). Documentation now names the product Cloudera Data Lineage, "the fusion of Octopai's metadata discovery engine with Cloudera's big data backbone" — [Cloudera Data Lineage overview](https://docs.cloudera.com/octopai/latest/getting-started/topics/oct-what-is-octopai-1.html); octopai.com now presents Cloudera Data Lineage — [octopai.com](https://www.octopai.com/)
- [vendor, datasheet] Integration with "60+ technologies out of the box", with column-level detail and cross-system lineage as core capabilities; a Custom Lineage Connector (formerly Universal Connector) covers non-native systems — [Cloudera Octopai datasheet](https://www.cloudera.com/content/dam/www/marketing/resources/datasheets/cloudera-octopai-data-lineage.pdf?daqp=true); [Custom Lineage Connector overview](https://docs.cloudera.com/octopai/latest/howto/topics/oct-custom-lineage-connector-overview.html)
- [doc] Lineage layers: cross-system lineage, inner-system lineage, end-to-end column lineage — [Inner System Lineage](https://docs.cloudera.com/octopai/latest/howto/topics/oct-inner-system-lineage.html)
- [doc] Databricks: column-level lineage for Unity Catalog and Hive Metastore only where column mappings exist in the metadata source; read from Unity Catalog system tables; SQL, Python and PySpark notebooks supported, Scala and R depend on Databricks providing lineage records; "high-volume environments use incremental mode" — [Databricks lineage in Cloudera Octopai](https://docs.cloudera.com/octopai/latest/getting-started/topics/oct-databricks-lineage.html); [Databricks Unity Catalog integration](https://docs.cloudera.com/octopai/latest/howto/topics/oct-databricks-unity-catalog-integration.html)
- [doc, Feb 2025] Hive connector with end-to-end column-level lineage; Impala added with cross-system and end-to-end column lineage — [Release notes, 3 Feb 2025](https://docs.cloudera.com/octopai/latest/release-notes/topics/oct-product-release-notes-feb-3rd-2025.html)
- [doc, Jun 2025] Apache NiFi connector shows only table-level cross-system lineage (column-level planned); "**streaming jobs (Spark Structured Streaming, Kafka) are not supported in this release**"; cross-system lineage connecting Informatica PowerCenter workflows with sources and targets — [Release notes, June 2025](https://docs.cloudera.com/octopai/latest/release-notes/topics/oct-product-release-notes-june-2025-edition.html)
- [doc, Jan 2026] Kerberos-backed Spark and Hive/Impala lineage, deeper Databricks and Snowflake coverage, "new streaming and pipeline connectors" — [Release notes, January 2026](https://docs.cloudera.com/octopai/latest/release-notes/topics/oct-product-release-notes-jan-2026.html)
- [doc, Mar 2026] Trino federated query engine supported, lineage kept across federated queries — [Release notes, March 2026](https://docs.cloudera.com/octopai/latest/release-notes/topics/oct-product-release-notes-mar-2026.html)
- [doc, Jun 2026] Expanded Microsoft Fabric coverage: the tool "parses the SQL, breaks down source columns, reflects transformations" — [Release notes, June 2026](https://docs.cloudera.com/octopai/latest/release-notes/topics/oct-product-release-notes-june-2026.html)
- [doc] dbt Cloud connector covers Snowflake, PostgreSQL, BigQuery, Redshift, Databricks and Spark SQL; Python-based dbt transformations do not generate lineage — [Configure dbt Cloud connector](https://docs.cloudera.com/octopai/latest/howto/topics/oct-dbt-cloud.html)
- [doc] Metadata extraction is automated with Microsoft Task Scheduler (client-side extractors on a schedule) — [Getting started guide](https://docs.cloudera.com/octopai/latest/getting-started/oct-getting-started.pdf)
- [doc] "Octomize AI - Lineage Studio empowered by GenAI Copilot" is documented — [Octomize AI](https://docs.cloudera.com/octopai/latest/howto/topics/oct-octomize-ai-lineage-studio-empowered-by-genai.html)
- [doc] A use-case page covers applying data lineage for data quality — [Use case: data lineage for data quality](https://docs.cloudera.com/octopai/latest/getting-started/topics/oct-practical-examples-of-how-to-apply-data-lineag.html)
- [3p, 2026] Independent review: historical lineage listed as a feature, "Lineage diff (not supported)" — [Data Stack Index: Cloudera Octopai review](https://datastackindex.com/data-observability/tools/cloudera-octopai/)
- [3p] A competitor page describes Octopai as "genuinely strong" at reading lineage out of legacy on-prem ETL and enterprise BI such as Informatica PowerCenter, SSIS, Cognos and SAP BusinessObjects — [DataTrail: Octopai alternative](https://datatrail.ai/alternatives/octopai)

### Inferences
- Mechanism class: **scheduled metadata extraction plus centralised parsing/analysis** (SaaS analysis of exported metadata), with system-table reads for Databricks. Latency is bounded by the extraction schedule (typically daily or weekly; the cadence was not stated in sources).
- O1 is strong for classic warehouse/ETL/BI estates; streaming was a stated gap in June 2025 and the January 2026 "streaming connectors" are not characterised, so Kafka/Flink column lineage should be assumed absent until shown.
- O2: scheduled re-extraction, incremental mode documented only for Databricks, historical lineage claimed by a third party, no diff.
- Cloudera ownership is shifting the roadmap toward Cloudera/Hadoop-lineage engines (Hive, Impala, NiFi, Trino, Spark with Kerberos), which is orthogonal to an AWS microservices/Kafka/feature-store estate.

### Gaps
- Native connector list with stored-procedure dialects, SSIS, DataStage, Talend, ADF, SSRS/SSAS, Power BI and Tableau depth: not confirmed from Cloudera docs.
- Lineage version comparison/time travel: not found.
- Pricing (list, AWS Marketplace, Vendr): not found.
- CI/CD or pull-request integration, MCP/agent features: not found.
- MTTR or productivity figures: not found.

---

## 6. Alation

### Takeaway
Alation derives lineage primarily from **query log ingestion (QLI)**, metadata extraction and its Compose query history, plus direct reads of platform lineage tables and an **OpenLineage ingestion endpoint**; 2026 updates added file-source, cross-database and OpenLineage coverage and view/dbt freshness. It offers an Impact Analysis report, a lineage API (v2 in 2026.7) and agent tooling, but stored-procedure-heavy transformation lineage is a reported weak spot and no CI/CD integration was found.

### Cited Findings
- [doc] Auto-generated lineage is "automatically generated by the system through query log ingestion (QLI), metadata extraction (MDE), and Compose object resolution pipelines"; "direct" lineage is obtained from system tables of certain databases (for example Databricks Unity Catalog); column-level lineage may need extra enablement per connector, and the supported-source list is in a version-specific Support Matrix — [Alation docs: Lineage glossary](https://docs.alation.com/en/latest/analyst/Lineage/LineageGlossary.html); [Alation docs: Discover lineage](https://docs.alation.com/en/latest/sources/Lineage/index.html)
- [doc] **OpenLineage integration**: events are sent to Alation's ingestion endpoint over HTTPS, authenticated with an Alation API token; Alation processes events and builds lineage — [Alation docs: OpenLineage integration](https://docs.alation.com/en/latest/cloud/OpenLineageIntegrations/index.html)
- [doc] Impact Analysis report "helps in assessing the impact from such changes as infrastructure migrations or product deployments"; a "distance" setting controls how many upstream/downstream nodes are included — [Alation docs: Lineage glossary](https://docs.alation.com/en/latest/analyst/Lineage/LineageGlossary.html)
- [vendor, Oct 2026] "Alation data lineage now covers file sources, cross-database moves, and OpenLineage events, and stays current as views and dbt models change"; Alation "can now build table- and column-level lineage between two RDBMS databases, whether data moves via queries or custom scripts, by matching object names across environments" when an admin declares the upstream source — [Alation blog: Data lineage updates, fuller, fresher graphs](https://www.alation.com/blog/alation-data-lineage-updates/)
- [3p, competitor-authored] From release 2024.1.2 Alation automatically captures SQL queries and generates column-level lineage; it is on by default for most connectors, with a few needing a feature flag — [Atlan: Alation adoption challenges](https://atlan.com/alation-data-catalog-adoption-challenges/)
- [doc, 2026] API release notes for 2026.7.2.0 list a "Lineage API v2"; the lineage API now excludes deleted objects by default — [Alation API release notes](https://developer.alation.com/dev/docs/running-api-release-notes). A public API can create and update lineage — [Alation developer portal: lineage overview](https://developer.alation.com/dev/reference/lineage-overview)
- [vendor, Aug 2026] **Critical Lineage** generally available 13 August 2026 for Alation Cloud Service, part of Critical Data Manager, consumes Alation Consumption Units (ACUs); aimed at end-to-end lineage for regulatory filings and critical reports — [Alation blog: Critical Lineage](https://www.alation.com/blog/critical-lineage-end-to-end-governance/)
- [3p citing TechTarget, 17 Sep 2026] Alation announced **agent lineage tracing** within its AI Governance expansion; some features are early access or limited in scope — [Maetra: Alation adds agent lineage](https://maetra.io/insights/alation-agent-lineage-ai-governance-data-context)
- [vendor repo] The Alation AI Agent SDK includes a lineage tool — [GitHub: alation-ai-agent-sdk lineage guide](https://github.com/Alation/alation-ai-agent-sdk/blob/main/guides/tools/lineage.md)
- [3p] A review says native lineage is well regarded for SQL and BI but less deep for complex ETL and stored procedures, citing a user report that transformation lineage "does not work" when transformations rely heavily on stored procedures, and that Alation historically leaned on Manta to fill the gap — [modern-datatools Alation review](https://www.modern-datatools.com/tools/alation)
- [press, Aug 2020, **stale**] Alation partnered with Manta for advanced lineage — [Business Wire](https://www.businesswire.com/news/home/20200820005284/en/Alation-Augments-Data-Lineage-Capabilities-With-Manta-Partnership)
- [3p] Pricing: AWS Marketplace 12-month contract "starting at $60,000" (units undefined, private offers); Vendr median about USD 141,394/yr, range USD 77,526-302,223 (sample size not stated) — [DataTrail: Alation pricing](https://datatrail.ai/alation-pricing). CostBench shows an outlier median of USD 580,725 from 4 reports — [CostBench](https://costbench.com/software/data-catalog/alation/)
- [press, 2024] A TechTarget article mentions integrations with Apache Kafka, MongoDB and Tibco Data Virtualization without lineage detail — [TechTarget](https://www.techtarget.com/searchdatamanagement/news/366573072/Alation-platform-update-targets-building-a-data-culture)

### Inferences
- Mechanism class: **query-log mining and SQL parsing** (runtime-observed SQL), **system-table reads**, **OpenLineage ingestion**, and name-matching for cross-database stitching. Query-log-based lineage only sees what has executed in the retained log window and is weak on procedural logic.
- O2: lineage refreshes with QLI/MDE runs and now tracks view and dbt model changes; no lineage versioning or diff surfaced.
- O3: Impact Analysis report and agent SDK tool; no pull-request check.
- "Critical Lineage" being consumption-priced (ACUs) means regulatory-grade lineage is an additional cost line.

### Gaps
- Stored-procedure and dynamic-SQL handling per connector: no Alation documentation found.
- Kafka/streaming and ML lineage: not found.
- Lineage history/time travel: not found.
- Gartner 2026 placement: not confirmed.
- MTTR/productivity figures: not found.
- Unverified background: Alation acquired Numbers Station in 2025 (not verified this session); status of the Manta partnership after IBM's acquisition is unknown.

---

## 7. Atlan

### Takeaway
Atlan combines **SQL parsing of warehouse query history**, **native API crawling** of BI/ETL tools and **OpenLineage ingestion** into one graph, and is the only vendor here with a documented **pull-request integration**: a GitHub Action (and GitLab equivalent) that comments downstream impact on dbt model and data-contract changes. It also exposes lineage tools through an MCP server. Its own docs acknowledge gaps for stored procedures, dynamic SQL and some connectors.

### Cited Findings
- [vendor] "Atlan's parser reads millions of SQL queries from data systems like Snowflake, BigQuery, Redshift, and Databricks to extract the actual transformation logic"; for tools SQL parsing cannot reach, Atlan "crawls each tool's native API to extract field-level dependencies, then stitches them into the same lineage graph" — [Atlan: data lineage](https://atlan.com/data-lineage.md)
- [vendor] "Atlan natively consumes OpenLineage events from Airflow, Spark, dbt Cloud, and Astronomer, capturing runtime inputs, outputs, and column-level transformations as pipelines execute" — [Atlan: data lineage](https://atlan.com/data-lineage.md)
- [doc] **GitHub impact analysis**: a GitHub Action adds downstream impact to pull requests when a dbt model changes; the comment includes impacted assets with descriptions, owners and linked glossary terms; configured via a workflow file with `GITHUB_TOKEN`, `ATLAN_INSTANCE_URL`, `ATLAN_API_TOKEN`, and optional `DBT_ENVIRONMENT_BRANCH_MAP` — [Atlan docs: add impact analysis in GitHub](https://docs.atlan.com/apps/connectors/etl-tools/dbt/how-tos/add-impact-analysis-in-github); [GitHub: atlanhq/atlan-action](https://github.com/atlanhq/atlan-action)
- [doc] `dbt-action` has been renamed `atlan-action`; setting `ATLAN_CONFIG` triggers impact analysis on Atlan **Data Contracts** in a pull request (labelled private preview) — [Atlan docs: migrate from dbt to Atlan action](https://docs.atlan.com/apps/connectors/etl-tools/dbt/how-tos/migrate-from-dbt-to-atlan-action); [Atlan docs: contract impact analysis in GitHub](https://docs.atlan.com/product/capabilities/governance/contracts/how-tos/add-contract-impact-analysis-in-github)
- [vendor] Atlan says it "calculates the full blast radius and surfaces it inside the GitHub or GitLab pull request, listing every downstream dashboard, pipeline, AI agent, and data product that would be affected" — [Atlan: data lineage](https://atlan.com/data-lineage.md)
- [vendor, 2026] **MCP server** lineage tools: `get_lineage`, `get_column_lineage`, `get_downstream_impact` with upstream/downstream and hop control; an MCP cookbook recipe covers "see what a SQL change will break before you merge" — [Atlan: MCP for data lineage](https://atlan.com/know/mcp/mcp-for-data-lineage/); [Atlan MCP cookbook](https://atlan.com/mcp-cookbook/see-what-a-sql-change-will-break-before-you-merge/)
- [vendor-claimed] "Workday saw a 5x improvement in AI response accuracy through Atlan's MCP server", which exposes column-level provenance "across 80+ systems" — [Atlan: MCP for data lineage](https://atlan.com/know/mcp/mcp-for-data-lineage/)
- [doc] BigQuery limitations: "Stored procedures and scalar UDFs don't appear as lineage-graph nodes. Dynamic SQL that calls routines at runtime, for example using EXECUTE IMMEDIATE, isn't captured" — [Atlan docs: BigQuery routines and process assets](https://docs.atlan.com/apps/connectors/data-warehouses/google-bigquery/faq/routines-and-process-assets)
- [doc, via search summary] dbt troubleshooting: "due to the limitations of SQL parsing, Atlan doesn't guarantee generating lineage for all columns"; the Matillion connector provides no end-to-end or column-level lineage because of source API limitations — surfaced alongside [Atlan docs: Talend lineage FAQ](https://docs.atlan.com/apps/connectors/etl-tools/talend/faq/talend-lineage) and [Power BI lineage reference](https://docs.atlan.com/apps/connectors/business-intelligence/microsoft-power-bi/references/what-lineage-does-atlan-extract-from-microsoft-power-bi) (exact page URLs for the dbt and Matillion statements were not returned)
- [vendor] Atlan's own article concedes SQL parsers "still struggle with dynamic SQL and stored procedures", leaving a small manual surface — [Atlan: automated SQL lineage vs manual mapping](https://atlan.com/know/ai-agent/data-for-ai/automated-sql-lineage-vs-manual-lineage-mapping/)
- [3p] Comparisons report that lineage through stored procedures "can stop at the CALL statement" and that Atlan's column-level links cover direct and conditional transformations while set-based operations (JOIN, FILTER, GROUP BY) are excluded as too broad — [daily.dev: Alation vs Atlan](https://daily.dev/posts/alation-vs-atlan-for-data-governance-where-each-one-wins-jvrf18qsd); [Decube: Atlan vs Purview](https://www.decube.io/post/atlan-vs-microsoft-purview-data-catalog) (attribution between the two pages uncertain)
- [doc] "Alert propagation" is documented under Atlan's lineage docs — [Atlan docs: lineage tag](https://docs.atlan.com/tags/lineage)
- [3p] Pricing: Vendr median USD 50,420/yr across 44 purchases, range about USD 30,000-178,000 (page updated Feb 2026) — [dataobservability.ai: Atlan pricing](https://dataobservability.ai/atlan-pricing); CostBench cites USD 49,764 (n=43) — [CostBench](https://costbench.com/software/data-catalog/atlan/); another site gives a mid-market median around USD 110,000 — [VendorBenchmark](https://vendorbenchmark.com/vendors/atlan-pricing). Atlan publishes no prices.
- [vendor] Atlan states it moved from Visionary (2025) to Leader in the 2026 Gartner MQ for D&A Governance Platforms, positioned highest on Ability to Execute — [Atlan: named a Leader](https://atlan.com/atlan-named-leader-in-gartner-da-governance-magic-quadrant/)

### Inferences
- Mechanism class: **query-history SQL parsing + API crawl + OpenLineage**. Good fit for a cloud-warehouse/dbt/Airflow stack; weaker for procedural code, and it has no code scanners for Java/COBOL.
- If the third-party claim is right that JOIN/FILTER/GROUP BY dependencies are excluded, Atlan captures **direct** but not **indirect** column lineage, which under-reports impact for filter/join-only dependencies.
- O3 is the strongest in the field for dbt-centric pipelines (pre-merge PR comments naming owners). It does not cover non-dbt code changes (stored procedures, Spark jobs, microservices) unless teams call the MCP/API themselves.
- O4: alert propagation along lineage exists; quantified MTTD/MTTR not surfaced.

### Gaps
- Kafka/Confluent/Flink lineage and ML model/feature-store (SageMaker, MLflow) lineage: **not searched** (budget exhausted). Unverified background: Atlan lists Kafka-family connectors.
- Lineage history/versioning/diff: not found.
- Incremental crawl behaviour and latency: not found.
- GitLab integration documentation: only the vendor marketing statement surfaced.
- Independent verification of the Workday 5x claim: none.

---

## 8. data.world (now part of ServiceNow)

### Takeaway
ServiceNow announced the acquisition of data.world in May 2025 (closed Q3 2025) to feed its Workflow Data Fabric; public evidence on data.world's own column-level lineage mechanism is thin and second-hand. The only description found says lineage comes from catalog collectors plus a self-hosted Manta technical lineage server, displayed in the Eureka Explorer graph.

### Cited Findings
- [press, 7 May 2025] ServiceNow announced it would acquire data.world to strengthen data catalog and governance for AI workflows; terms undisclosed — [TechCrunch](https://techcrunch.com/2025/05/07/servicenow-acquires-data-world-two-months-after-acquiring-moveworks); [Constellation Research](https://www.constellationr.com/insights/news/servicenow-launches-workflow-data-network-acquires-dataworld)
- [vendor] ServiceNow's press page says the deal closed in Q3 2025 — [ServiceNow press room: Workflow Data Fabric](https://www.servicenow.com/de/company/media/press-room/workflow-data-fabric-ai-agents.html)
- [press] Coverage describes data.world's knowledge graph and metadata collectors becoming part of ServiceNow's data platform — [TechTarget](https://www.techtarget.com/searchitoperations/news/366623687/ServiceNow-digs-deeper-into-data-for-AI-with-Dataworld-buy)
- [3p directory, 2026] "Data.World by ServiceNow": catalog collectors and a self-hosted MANTA technical lineage server together produce lineage at table, column and query level, displayed in an Eureka Explorer graph — [DBMS Tools: SQL lineage tools](https://dbmstools.com/categories/sql-lineage-tools)
- [vendor] Manta lists a data.world integration — [manta.io: data.world integration](https://manta.io/integrations/data.world)

### Inferences
- data.world's deep (code-parsed) column lineage appears to be **Manta-supplied** rather than native; with Manta now IBM-owned and data.world ServiceNow-owned, continuity of that integration is a risk to verify.
- Not a credible standalone answer to O1-O4 on current evidence.

### Gaps
- Official data.world/ServiceNow documentation on lineage mechanism, coverage, incremental behaviour, impact analysis: not found (query did not run).
- Product naming and roadmap inside ServiceNow in 2026, pricing, deployment: not found.

---

## 9. Quest erwin Data Intelligence (renamed Quest Data Intelligence)

### Takeaway
erwin Data Intelligence was renamed **Quest Data Intelligence** with version 16 (announced 13 May 2026). Lineage is built from metadata harvested by 100+ standard connectors (data at rest) and optional, separately licensed **Smart Data Connectors** that reverse-engineer ETL, code and BI ("data in motion"); version 16 adds AI assistants including one for lineage. No evidence of incremental lineage versioning or CI/CD integration surfaced.

### Cited Findings
- [vendor] With version 16 the product was renamed from erwin Data Intelligence by Quest to Quest Data Intelligence — [Quest blog](https://blog.quest.com/?p=31977). Support page: 16.0 fully supported from 28 May 2026; 15.0 from 12 May 2025 — [Quest support: Quest Data Intelligence](https://support.quest.com/quest-data-intelligence/11.0)
- [press, 13 May 2026] Quest announced Quest Data Modeler and Quest Data Intelligence with assistants spanning glossary and ownership, data lineage, compliance, data products and data quality — [Quest press release](https://www.quest.com/news/press-releases/quest-software-enhances-its-trusted-data-management-platform-with-quest-data-modeler-and-quest-data-intelligence/)
- [doc, 16.0] QuestAI hub with a Universal Semantic Assistant routing to specialised assistants (catalog, lineage, glossary and ownership, marketplace, stewardship); Policy Manager that generates enforcement rules and SQL scripts with AI; Enterprise Tag Groups with Tag Lineage — [Quest DI 16.0 release notes](https://bookshelf.quest.com/bookshelf/16.0DIBookshelf/Content/Release%20Notes/New%20Features%20and%20Enhancements-Online.html); [PDF](https://support-public.cfm.quest.com/82818_Quest_DI_Release_Notes_v16.0.pdf)
- [doc, 16.2] Ability to generate lineage using only source and target systems/environments; lineage diagrams sort tables and columns alphabetically — [Quest DI release notes](https://bookshelf.quest.com/bookshelf/16.0DIBookshelf/Content/PDFs/Quest%20DI%20Release%20Notes.pdf)
- [vendor] Lineage is generated "down to the column level", upstream and downstream from source systems to reporting — [erwin Data Catalog datasheet](https://origin.quest.com/documents/erwin-data-catalog-datasheet-147777.pdf)
- [vendor] **Smart Data Connectors** are optional add-ons capturing metadata from data in motion for lineage, versus included Standard connectors for data at rest; product page cites more than 100 data connectors — [Quest: erwin Data Connectors](https://origin.quest.com/products/erwin-data-connectors); [Quest: erwin Data Intelligence](https://www.quest.com/products/erwin-data-intelligence)
- [vendor] A SaaS edition is listed on Microsoft's marketplace ("erwin DI cloud") — [Microsoft Marketplace](https://marketplace.microsoft.com/en-my/product/quest.erwin_di_cloud)

### Inferences
- Mechanism class: **metadata harvest plus mapping-centric lineage**; code/ETL-level lineage depends on purchasing the relevant Smart Data Connectors, so total cost and coverage are connector-by-connector.
- Lineage derives from the mapping repository (source-to-target mappings), which historically makes it as current as the last connector run; nothing surfaced on revisioning or diff.
- 2026 investment is in conversational assistants and policy automation, not in engineering-workflow integration.

### Gaps
- List of Smart Data Connectors (SSIS, Informatica, DataStage, PL/SQL, T-SQL, Python, COBOL) and their column-level depth: not found (query did not run).
- Incremental scan, lineage history/diff, impact-analysis specifics in 16.x: not found.
- Pricing: not found.
- Kafka/streaming, ML lineage, OpenLineage support, MCP: not found.

---

## 10. Rocket Software Data Intelligence (ex-ASG)

### Takeaway
Rocket Data Intelligence (part of Rocket DataEdge) is the mainframe-heavy option: scanners for COBOL, JCL, CICS, Db2 for z/OS, IMS, Adabas/Natural, CA-IDMS and Assembler alongside distributed ETL, databases and code. In July 2026 Ataccama made Rocket's scanners a supported lineage source inside Ataccama ONE. Evidence on column-level depth, incremental behaviour and pricing is thin and mostly from listings.

### Cited Findings
- [vendor] Rocket Data Intelligence delivers enterprise data lineage across hybrid and multi-cloud environments as part of Rocket DataEdge — [Rocket Data Intelligence product page](https://www.rocketsoftware.com/products/rocket-data-intelligence); [Rocket DataEdge](https://www.rocketsoftware.com/en-us/products/dataedge)
- [vendor, 2026] Named Most Innovative Data Lineage Solution at the 2026 A-Team Data Management Insight Innovation Awards — [Rocket: 2026 award](https://www.rocketsoftware.com/en-us/insights/rocket-software-wins-2026-award-most-innovative-data-lineage-solution)
- [press, June 2023, **stale**] At launch the product supported "a catalog of 200 connectors and scanners", including IBM mainframes and IBM i — [BigDATAwire, 19 Jun 2023](https://www.bigdatawire.com/2023/06/19/rocket-launches-a-choose-your-own-adventure-for-data-lineage-tracking)
- [partner, Jul 2026] Ataccama: "Rocket's scanners function as fully supported lineage sources within Ataccama ONE"; mainframe coverage includes COBOL for z/OS, CICS, JCL, Db2 for Z, Assembler for z/OS, IMS, ADABAS, NATURAL and CA-IDMS/DB; there is "no direct runtime connection" between Rocket's scanners and Ataccama ONE; Rocket-sourced lineage metadata is "indistinguishable" from Ataccama's own — [Ataccama blog: closing the lineage gap](https://ataccama.com/blog/closing-the-lineage-gap-how-ataccama-and-rocket-software-deliver-true-end-to-end-lineage)
- [3p listing] Supported platforms listed as Db2, VSAM, IMS, Adabas, Datacom, relational databases, ETL tools such as Informatica and DataStage, and code such as COBOL, Python and Java; features listed include "Database Change Impact Analysis" and "Point-in-Time Visibility"; field/column-level tracing "where supported" — [Slashdot comparison listing](https://slashdot.org/software/comparison/Rocket-Data-Intelligence-vs-Rocket-Relativity/)
- [vendor] A data lineage brochure exists (contents not retrievable) — [Rocket Data Lineage Brochure](https://www.rocketsoftware.com/sites/default/files/resource_files/Data-Lineage-Brochure.pdf)

### Inferences
- Mechanism class: **static source-code and metadata scanners**, in the same family as Manta, with the broadest mainframe language set evidenced here.
- The Ataccama arrangement is file/metadata hand-off (no runtime connection), implying batch latency.
- "Point-in-Time Visibility" suggests some historical lineage capability, but mechanism is undocumented in what was retrieved.

### Gaps
- Column-level lineage through COBOL (MOVE/COMPUTE-level field tracing) versus program-to-dataset level: not confirmed.
- Current scanner count, incremental scanning, diff, CI/CD, OpenLineage, MCP, pricing, deployment: not found.
- Unverified background: the product descends from ASG Technologies' Data Intelligence (ASG acquired by Rocket Software around 2021); not sourced this session.

---

## 11. Ataccama (ONE)

### Takeaway
Ataccama moved from embedding Manta (docs up to v15) to **its own lineage scanners** in ONE v16-v17, with a documented set including dbt, Power BI, SSIS, BigQuery, Databricks, Azure Data Factory and an OpenLineage scanner, and it partners with Rocket for mainframe. Its docs are candid about limits (dbt tests unsupported, attribute lineage only with catalog.json, SSIS single-statement SQL only, Power BI Dataflows Gen2 unsupported); its differentiator is overlaying data quality on lineage.

### Cited Findings
- [doc, older versions] Ataccama ONE 14.5.x/15.2 lineage documentation lists connection types taken from MANTA, including Informatica PowerCenter and IBM InfoSphere DataStage — [Ataccama docs 14.5.x lineage](https://docs.ataccama.com/one/14.5.x/lineage/lineage.html)
- [press, date not shown in results] TechTarget reported Ataccama adding data lineage to foster trust in AI analytics — [TechTarget](https://www.techtarget.com/searchDataManagement/news/366619203/Ataccama-adds-data-lineage-to-foster-trust-in-AI-analytics). ONE v16.2 (July 2025) added AI-powered lineage and compact lineage diagrams — [IT Brief](https://itbrief.com.au/story/ataccama-one-v16-2-uses-ai-to-simplify-data-lineage-for-business)
- [vendor] Column-level lineage tracking from source to consumption; lineage scans metadata across sources, ETL jobs and destinations, "powered by the ONE AI Agent" — [Ataccama: data lineage](https://www.ataccama.com/platform/data-lineage)
- [vendor, Jul 2026] ONE "ships with built-in scanners for the platforms most enterprises use every day — Snowflake, Oracle, dbt, Power BI, and many other common technologies" — [Ataccama blog on Rocket partnership](https://ataccama.com/blog/closing-the-lineage-gap-how-ataccama-and-rocket-software-deliver-true-end-to-end-lineage)
- [doc] A "supported lineage technologies" page exists for the current release (v17.x) — [Ataccama docs: supported lineage technologies](https://docs.ataccama.com/one/latest/lineage/supported-lineage-technologies.html); [v17.0.0 get started](https://docs.ataccama.com/one/17.0.0/lineage/get-started.html)
- [doc] **dbt scanner**: supports dbt Core and Cloud; "dbt tests are currently not supported"; attribute lineage only when dbt documentation generation is enabled (catalog.json available); other ANSI-SQL databases "can be supported with minimal effort" — [Ataccama docs: dbt lineage scanner](https://docs.ataccama.com/one/latest/lineage/dbt-lineage-scanner.html)
- [doc] **Power BI scanner**: Dataflows Gen2 not supported; functions such as List.Dates and other calendar functions not supported; nested dataflows unsupported — [Ataccama docs: Power BI scanner features and limitations](https://docs.ataccama.com/one/latest/lineage/powerbi-lineage-features.html)
- [doc] **SSIS scanner**: "Queries containing multiple statements (for example, using DECLARE before SELECT, or any batch execution) are not processed" — [Ataccama docs: MS SSIS lineage scanner](https://docs.ataccama.com/one/latest/lineage/ssis-lineage-scanner.html)
- [doc, 16.2] **OpenLineage scanner**: documented source formats are file-based in AWS S3 (CSV, Excel, Parquet, Iceberg); a valid graph is generated only for events whose inputs and outputs arrays are non-empty — [Ataccama docs: OpenLineage scanner](https://docs.ataccama.com/one/16.2.0/lineage/openlineage-scanner.html)
- [doc] BigQuery, Databricks and Azure Data Factory scanners are documented — [BigQuery](https://docs.ataccama.com/one/latest/lineage/bigquery-lineage-scanner.html); [Databricks](https://docs.ataccama.com/one/latest/lineage/databricks-lineage-scanner.html); [Azure Data Factory](https://docs.ataccama.com/ataccama-one-agentic/latest/lineage/azure-data-factory-lineage-scanner.html)
- [3p] A competitor page counts roughly eighteen scanners — [DataTrail: Ataccama alternative](https://datatrail.ai/alternatives/ataccama)
- [vendor] Ataccama published a blog on the 2026 Gartner MQ for D&A Governance Platforms (its placement not confirmed in the snippet) — [Ataccama blog](https://www.ataccama.com/blog/gartner-magic-quadrant-for-data-and-analytics-governance-platforms-2026-explained-what-changed-this-year)

### Inferences
- Mechanism class: **native scanners (metadata + SQL parsing) + OpenLineage + partner scanners (Rocket)**; scanner breadth (~18) is well below Manta/Rocket/Octopai.
- The SSIS single-statement restriction and the absence of surfaced stored-procedure pages suggest procedural SQL coverage is limited.
- Ataccama's value for O4 is that DQ results and lineage live in one platform, so a failed rule can be traced upstream; no figures surfaced.

### Gaps
- Contents of the v17 supported-technologies table, stored-procedure support, Snowflake/Oracle scanner limitations: not retrieved.
- Incremental scans, lineage history/diff, CI/CD, MCP, Kafka/ML lineage, pricing: not found.
- When exactly the Manta dependency was dropped: not confirmed.

---

## 12. Precisely (Data360 Govern / Data Integrity Suite)

### Takeaway
Current Precisely lineage evidence is for the **Data Integrity Suite** rather than Data360 Govern: it harvests **static lineage** (from metadata definitions) and **operational lineage** (from runtime execution, for example Snowflake `ACCESS_HISTORY` and the Databricks `column_lineage` system table) at field/column level, and ingests **OpenLineage** events through an API endpoint. Coverage appears narrow and cloud-warehouse-centric; no evidence of code scanners for stored procedures, legacy ETL or mainframe.

### Cited Findings
- [vendor engineering blog] "For each source, the Data Integrity Suite harvests static and/or operational lineage at the field and column level and persists this as lineage within the Data Catalog"; static lineage is derived from metadata definitions and operational lineage from pipeline runs; operational lineage is drawn from Snowflake's `ACCESS_HISTORY` view and Databricks' `column_lineage` system table — [Precisely: From fragments to flow](https://www.precisely.com/blog/engineering/from-fragments-to-flow-how-the-precisely-data-integrity-suite-builds-data-lineage/)
- [vendor] When a data quality rule fails, lineage can be traced upstream from the failing column to the source system or pipeline behind the anomaly — [Precisely: From fragments to flow](https://www.precisely.com/blog/engineering/from-fragments-to-flow-how-the-precisely-data-integrity-suite-builds-data-lineage/)
- [vendor engineering blog] **OpenLineage**: unifies lineage from Airflow, Spark, dbt, Dagster and others; events are posted to `POST /v2/catalog/lineage` through the Precisely API Gateway; column-level lineage "is captured only when supported by the producer"; events are processed idempotently so replays do not create duplicate relationships — [Precisely: OpenLineage integration](https://www.precisely.com/blog/engineering/openlineage-integration-bridging-open-standards-with-the-precisely-data-integrity-suite/)
- [3p listing] Data360 Govern is described as offering an automatically generated field-level lineage map — [SourceForge comparison listing](https://www.sourceforge.net/software/compare/Data360-Govern-vs-Validio)
- [vendor, 2026] A June 2026 Precisely data governance product sheet exists (contents not retrieved) — [Precisely product sheet PDF](https://www.precisely.com/wp-content/uploads/2026/06/PS_Data-Governance_260623_E_final.pdf)

### Inferences
- Mechanism class: **platform-native lineage views (query/access history) + OpenLineage ingestion**, i.e. Precisely relies on what the warehouse or the producer already knows rather than parsing code itself.
- Operational lineage from access history is inherently incremental (it reflects what ran), which helps O2 freshness but gives no pre-change view for O3.
- Data360 Govern looks like the legacy line with investment going to the Data Integrity Suite; not confirmed.

### Gaps
- Status/roadmap of Data360 Govern (end of sale, migration path): not found (query did not run).
- Connector list, stored-procedure/ETL-tool/BI lineage, incremental behaviour, impact analysis, CI/CD, pricing: not found.

---

## 13. Alex Solutions, Zeenea (HCLSoftware/Actian) and Orion Governance EIIG (time-permitting vendors)

### Takeaway
Evidence for these three is sparse. Orion EIIG is the only one with a concrete element-level mechanism claim (70+ "ingestors" including mainframe, ETL, BI and Python/Java/COBOL into a knowledge graph); Zeenea's lineage is largely API-fed at field level; Alex markets automated column-level lineage but mechanism detail was not found.

### Cited Findings

**Alex Solutions**
- [3p listing] Alex positions itself as a unified active metadata fabric for data and AI governance (catalog, lineage, quality, policy, privacy); marketplace copy claims "column-level granularity and in-lineage hierarchies" — [SoftwareOne: Alex Automated Data Lineage](https://platform.softwareone.com/product/alex-automated-data-lineage/PCP-6009-9395)
- [3p, Oct 2025] Gartner Peer Insights listing describes automated data lineage as the central feature — [Gartner Peer Insights: Alex](https://www.gartner.com/reviews/market/active-metadata-management/vendor/alex-solutions/product/alex)

**Zeenea (HCLSoftware / Actian)**
- [press] HCLSoftware announced its intent to acquire Zeenea on 8 August 2024 and completed it on 12 September 2024, placing it within the Actian division; reported price about EUR 24M — [HCLSoftware announcement](https://www.hcl-software.com/news/08-08-24-hclsoftware-announces-intent-to-acquire-metadata-management-software-provider-zeenea); [PR Newswire completion](https://www.prnewswire.com/in/news-releases/hclsoftware-completes-acquisition-of-metadata-management-software-provider-zeenea-302247177.html); [BusinessWorld](https://businessworld.in/article/hclsoftware-to-acquire-french-data-governance-firm-zeenea-for-%E2%82%AC24-mn-529112)
- [vendor] Field-level lineage: input and output fields are added through the Catalog API and field-level transformations are shown in a graph — [Zeenea feature note: data lineage](https://zeenea.com/product-updates/feature-note-data-lineage); product page — [Actian Zeenea data lineage](https://actian.com/zeenea/data-lineage)

**Orion Governance EIIG**
- [vendor, AWS Marketplace] Enterprise Information Intelligence Graph has "dedicated ingestors for 70+ technology sources from the mainframe, DBMSs, ETL and BI tools, and programming languages such as Python, Java, COBOL" — [AWS Marketplace: Orion EIIG](https://aws.amazon.com/marketplace/pp/prodview-4n2trutab22h2)
- [press, June 2022, **stale**] EIIG traces information flow in AS/400 through RPG, Java, Python, COBOL and SQL — [GlobeNewswire](https://www.globenewswire.com/news-release/2022/06/20/2465507/0/en/Orion-Governance-Announces-the-Support-of-the-Most-Popular-IBM-Technologies-the-AS400-RPG-Programming-Language.html); a 2022 deck lists SAS and COBOL/JCL sources — [Dataversity demo day deck](https://content.dataversity.net/rs/656-WMW-918/images/DVDemoDay-DC-Orion.pdf)
- [press, undated in results] Orion announced a "competitive takeout program for legacy data/AI governance platforms" — [EIN Presswire](https://www.einpresswire.com/article/880901498/orion-governance-announces-competitive-takeout-program-for-legacy-data-ai-governance-platforms)
- [analyst listing] BARC lists EIIG, largely as vendor self-description without user reviews — [BARC review page](https://barc.com/de/review/orion-governance-enterprise-information-intelligence-graph-eiig/)

### Inferences
- Orion EIIG belongs to the static-code-scanner family (like Manta and Rocket) and is purchasable through AWS Marketplace, which is relevant for an AWS-centred buyer, but independent validation is absent.
- Zeenea's lineage depends on what connectors or customers push through the API; it is not a code-parsing engine.

### Gaps
- For all three: scanner lists, column-level depth, O2/O3/O4 features, pricing and any 2025-2026 release detail were not found.
- Alex: mechanism (parser vs metadata) not found. Orion: AWS Marketplace price not captured.

---

## 14. Cross-vendor evidence: analysts, independent reviews, streaming/ML coverage and MTTD/MTTR figures

### Takeaway
Analyst coverage confirms market standing (Collibra, Informatica, IBM and Atlan all claim Leader status in Gartner's 2026 governance MQ) but says little about element-level mechanism. No vendor-specific, lineage-attributable MTTD/MTTR figure was found for any in-scope vendor, and no in-scope vendor produced documented evidence of column-level lineage through microservices, Kafka/Flink or feature stores other than via OpenLineage ingestion.

### Cited Findings
- [vendor statements about analyst report] Leaders claimed in the 2026 Gartner Magic Quadrant for Data and Analytics Governance Platforms: Collibra (third year running), Informatica, IBM, Atlan (up from Visionary in 2025) — [Collibra](https://www.collibra.com/resources/2026-gartner-magic-quadrant-for-data-analytics-platforms); [Informatica](https://www.informatica.com/data-governance-magic-quadrant.html); [IBM](https://www.ibm.com/forms/mkt-report-0d537); [Atlan](https://atlan.com/atlan-named-leader-in-gartner-da-governance-magic-quadrant/). Publication date conflicts across sources: Gartner's abstract and Informatica indicate 6 January 2026, while Atlan and some IBM material cite 12 November 2026 — [Gartner abstract](https://www.gartner.com/en/documents/7315430); [Atlan: MQ November 2026](https://atlan.com/know/gartner/magic-quadrant-for-data-governance-november-2026/)
- [analyst, Q3 2025] The Forrester Wave: Data Governance Solutions, Q3 2025 evaluated 13 providers and framed governance as entering "the agentic era" — [Forrester blog](https://forrester.com/blogs/the-forrester-wave-data-governance-solutions-q3-2025-shows-that-governance-entered-the-agentic-era). Second-hand summaries name Collibra a Leader, cite lineage analysis and observability as differentiators, note IBM's integration with Manta, and say BigID's lineage lagged — [summary blog](https://masterdatamanagementconcept.blogspot.com/2025/07/forrester-wave-data-governance.html); [NHIMG commentary](https://nhimg.org/articles/forresters-data-governance-wave-signals-a-wider-ai-governance-shift/)
- [3p vendor blog] Why parser-based lineage is weak on procedural code: most parsers handle declarative SQL (SELECT/INSERT/UPDATE/DELETE/CREATE VIEW) but not loops, branches, cursors and dynamic SQL; catalogs "have added stored procedure support in their UI, but the actual parsing for lineage extraction is not there" — [dpriver.com blog](https://www.dpriver.com/blog/why-most-sql-lineage-tools-skip-stored-procedures-and-what-you-can-do-about-it/) (authored by a SQL-lineage tool vendor, so not neutral)
- [3p guide] Stored procedures, UDFs and non-SQL Spark code "usually collapse to a table-level edge or vanish"; `SELECT *` without known schema falls back to table-level — [datadef.io: column-level lineage explained](https://datadef.io/guides/en/column-level-lineage-explained)
- [context, out-of-scope tools] Kafka column-level lineage generally depends on schema-registry metadata: DataHub's plain Kafka source marks column-level lineage as not supported while its Kafka Connect source can derive it by field-name matching when both sides' schemas are ingested — [DataHub docs: Kafka](https://docs.datahub.com/docs/generated/ingestion/sources/kafka); [DataHub docs: Kafka Connect](https://docs.datahub.com/docs/generated/ingestion/sources/kafka-connect)
- [vendor-commissioned, different vendor] The only quantified lineage-related figure surfaced was for OvalEdge (out of scope): effort to catalog metadata, fulfil data requests and compile lineage reduced "by up to 40%" in a commissioned study — [OvalEdge blog](https://www.ovaledge.com/blog/data-lineage-explained-with-examples)
- [vendor-claimed] Atlan cites a Workday "5x improvement in AI response accuracy" via its MCP server (accuracy, not MTTR) — [Atlan: MCP for data lineage](https://atlan.com/know/mcp/mcp-for-data-lineage/)
- [vendor-commissioned] Forrester's TEI of Informatica IDMC mentions lineage-aided troubleshooting qualitatively, with no MTTR percentage in the retrieved excerpt — [Forrester TEI: Informatica IDMC](https://tei.forrester.com/go/informatica/IDMC/index.html?lang=en-us)

### Inferences
- **Mechanism taxonomy across the field:** (a) static code/metadata scanners (IBM Manta, Rocket, Orion, Octopai, Informatica, Quest Smart Data Connectors, Collibra's SQL parser, Ataccama's scanners); (b) query-log/query-history parsing (Alation, Atlan); (c) platform lineage tables (Unity Catalog `column_lineage`, Snowflake `ACCESS_HISTORY`, Dataplex) used by Collibra, Octopai, Alation, Precisely; (d) OpenLineage runtime events, now ingested by IBM, Collibra, Alation, Atlan, Solidatus, Ataccama and Precisely, and emitted by IBM; (e) curated/modelled lineage (Solidatus, Zeenea API, Informatica custom metadata, IBM Custom Lineage Mappings).
- **OpenLineage has become the de facto bridge** for Spark, Airflow, dbt and custom pipelines, but every vendor that documents it also documents that column-level detail arrives only if the producer emits the column-lineage facet, and IBM users report the transformation sub-fields being dropped.
- **For the buyer's estate (microservices -> Kafka/Flink -> warehouse -> feature store -> ML model on AWS):** commercial tools evidence solid coverage only for the warehouse leg (plus dbt/Airflow/Spark). Microservice-to-topic, topic-to-Flink and feature-store-to-model lineage would have to be emitted by the buyer (OpenLineage or custom API) and stitched in the tool; none of the vendors documented native column-level lineage for those hops in what was retrieved.
- **O2 and O3 are the weakest objectives market-wide.** Only IBM Manta (revisions, targeted scans) and Solidatus (bi-temporal versions) evidence real lineage history; only Atlan evidences pre-merge pull-request checks. The 2026 industry direction is MCP servers exposing lineage to agents (IBM, Collibra, Informatica, Solidatus, Atlan, Alation's agent SDK), which makes PR-time impact analysis something a buyer can assemble but not something most vendors ship.
- **O4:** every vendor asserts lineage-based root-cause analysis; none published a verifiable MTTD/MTTR number in the retrieved material.

### Gaps
- Bloor Research data lineage market update (2025/2026) and BARC Score for data intelligence platforms: not found.
- Gartner MQ quadrant placements for Alation, Ataccama, Quest, Precisely, Solidatus: not confirmed; the Gartner publication date conflict (January vs November 2026) is unresolved, and there may be two editions.
- Practitioner evidence (Reddit r/dataengineering, G2, Gartner Peer Insights) specific to these vendors' column-level lineage: search returned none.
- Vendor MTTD/MTTR case-study figures: the dedicated query did not run.
- Unverified background: Apache Flink has an OpenLineage integration; not sourced this session.

---

## 15. Comparison table and open questions

### Takeaway
On the retrieved evidence, IBM Manta is the strongest for baseline depth and lineage history, Atlan for pre-merge change impact on a modern stack, Solidatus for versioned/what-if modelling, Rocket/Orion for mainframe code, and Octopai for legacy ETL/BI; none demonstrably covers the buyer's microservices-Kafka-Flink-feature-store path without buyer-emitted OpenLineage or custom lineage, and none publishes verifiable MTTR figures.

### Cited Findings
- All cells in the table below summarise the cited findings in sections 1-14; sources are linked there. Ratings are the researcher's inference, not vendor or analyst scores.

### Inferences

Rating key: **Strong** = documented capability with specifics; **Partial** = capability exists with documented limits or only vendor claims; **Weak** = third-party evidence says absent or limited; **n/e** = not evidenced in retrieved material.

| Vendor | Mechanism for element-level lineage | O1 Baseline | O2 Incremental / history | O3 Change impact (pre-merge) | O4 Incident RCA | Pricing evidence | Key limitation |
|---|---|---|---|---|---|---|---|
| **IBM Manta / watsonx.data intelligence** | Static code + metadata scanners (SQL, stored procs, ETL, BI, COBOL/JCL, SAS); OpenLineage import and export; Custom Lineage Mappings | **Strong**: column-level, direct vs indirect, transformation logic | **Strong/Partial**: revisions as snapshots; Targeted scans start from last revision; two-revision diff disputed | **Partial**: interactive impact analysis, managed MCP server (Apr 2026); no CI/PR integration found | **Partial**: historical lineage for RCA; no MTTR figures | Custom quote; 1 RU = 30,000 scripts (CP4D) or 1 data source / 5,000 tables (SaaS); CDW.ca CAD ~139.6K per RU | Dynamic SQL mostly unsupported; no native dbt/Airflow scanners; COBOL dynamic calls; heavy footprint; OpenLineage column transformations not parsed (user report, Jan 2026) |
| **Collibra Data Lineage** | SQL parsing via Edge (harvester EOL 31 Jul 2026); OpenLineage (Airflow, Glue, dbt); system tables (Unity Catalog, Dataplex) | **Partial**: per-source matrix, stored procs vary, BI stitching gaps | **n/e**: sync behaviour, history, diff not found | **Partial**: lineage read APIs + MCP ("impact analysis before a change ships"); no PR check found | **n/e** | No list price; Vendr avg ~USD 166K (n=5); CostBench ~USD 170-197K | Cursors/dynamic SQL unsupported; Redshift procs unsupported; Glue DynamicFrames; Power BI DirectQuery excluded; lineage cloud-only |
| **Informatica CDGC (Salesforce)** | Catalog-source scanners via Secure Agent (PowerCenter, IDMC, RDBMS, scripts, BI); custom metadata; CLAIRE lineage agent | **Strong/Partial**: column-to-column for Informatica ETL and RDBMS; ~99 source types (3p) | **Weak**: historical lineage and diff "not supported" (3p) | **Partial**: impact analysis; MCP servers (2026); no CI/PR | **Partial**: qualitative TEI mention only | IPU consumption; price points not found | No lineage history; parameter-file dependencies; roadmap now Salesforce-driven; Kafka/COBOL coverage unconfirmed |
| **Solidatus** | Connector harvest + OpenLineage + manual/AI-assisted modelling in a versioned graph | **Partial**: vendor-claimed column-level and stored-proc parsing | **Strong (vendor-claimed)**: bi-temporal versioning, run consolidation, what-if | **Partial**: what-if models, MCP (2026.3); no CI/PR | **n/e** | Not found | Evidence almost entirely vendor-authored; connector depth unknown; curated lineage effort |
| **Cloudera Octopai** | Scheduled metadata extractors + central parsing; system tables for Databricks; Custom Lineage Connector | **Strong** for legacy ETL/BI and Cloudera engines; column-level across 60+ techs | **Partial**: scheduled extraction, incremental mode (Databricks), history claimed, no diff (3p) | **n/e** beyond interactive impact analysis | **Partial**: DQ use-case doc | Not found | Streaming (Kafka, Structured Streaming) unsupported as of Jun 2025; NiFi table-level only; Python dbt models; roadmap tilting to Cloudera stack |
| **Alation** | Query log ingestion + metadata extraction + Compose; system tables; OpenLineage endpoint; name-matching across DBs | **Partial**: good for SQL/BI, weak for stored-proc-heavy ETL | **Partial**: refresh with QLI/MDE; tracks view/dbt changes (Oct 2026); no versioning found | **Partial**: Impact Analysis report, Lineage API v2, agent SDK; no CI/PR | **n/e** | AWS Marketplace from USD 60K/12 months; Vendr median ~USD 141K | Query-log blind spots (un-run code, procedural logic); Critical Lineage is consumption-priced add-on |
| **Atlan** | Query-history SQL parsing + native API crawl + OpenLineage | **Partial/Strong** on modern stack; direct lineage only per 3p (JOIN/FILTER excluded) | **n/e** (no history/diff found) | **Strong**: GitHub/GitLab PR comments for dbt and data contracts (contracts in preview); MCP lineage tools | **Partial**: alert propagation along lineage | No list price; Vendr median ~USD 50K (n=44), range ~30-178K | Stored procs and dynamic SQL not captured (BigQuery docs); no code scanners; some connectors lack column lineage (Matillion) |
| **data.world (ServiceNow)** | Catalog collectors + self-hosted Manta lineage server (3p description) | **n/e/Weak** natively | **n/e** | **n/e** | **n/e** | Not found | Deep lineage appears dependent on IBM-owned Manta; product direction inside ServiceNow unclear |
| **Quest Data Intelligence (erwin)** | Standard connectors (data at rest) + optional Smart Data Connectors (ETL/code/BI) feeding mapping-based lineage | **Partial**: column-level claimed; depth depends on add-on connectors | **n/e** | **Partial**: impact analysis; AI lineage assistant (v16, May 2026) | **n/e** | Not found | Code/ETL lineage requires separately licensed connectors; no evidence of versioning or CI/CD |
| **Rocket Data Intelligence (ASG)** | Static scanners incl. mainframe (COBOL, JCL, CICS, IMS, Adabas/Natural, IDMS, Assembler), ETL, DBs, Python/Java | **Strong (claimed)** for mainframe; column-level "where supported" | **Partial**: "point-in-time visibility" listed | **Partial**: "database change impact analysis" listed | **n/e** | Not found | Thin public documentation; column-level depth in COBOL unconfirmed; 200-connector figure is from 2023 |
| **Ataccama ONE** | Native scanners (~18) + OpenLineage scanner + Rocket scanners for mainframe; formerly embedded Manta | **Partial**: documented scanner limits | **n/e** | **n/e** | **Partial**: DQ + lineage in one platform | Not found | dbt tests unsupported; SSIS single-statement SQL only; Power BI Gen2 dataflows unsupported; OpenLineage scanner scoped to S3 file formats (16.2) |
| **Precisely (Data Integrity Suite / Data360 Govern)** | Static lineage from metadata + operational lineage from Snowflake ACCESS_HISTORY and Databricks column_lineage; OpenLineage API | **Partial**: column-level for supported cloud platforms | **Partial**: operational lineage reflects runs | **n/e** | **Partial**: DQ-rule failure traced upstream | Not found | No evidence of code/ETL/stored-proc scanners; Data360 Govern status unknown |
| **Orion Governance EIIG** | 70+ "ingestors" (mainframe, DBMS, ETL, BI, Python/Java/COBOL) into a knowledge graph | **Partial (claimed)** | **n/e** | **n/e** | **n/e** | On AWS Marketplace; price not captured | No independent validation; most public material dates from 2022 |
| **Zeenea (Actian/HCLSoftware)** | Connectors + Catalog API-fed field-level lineage | **Weak/Partial** | **n/e** | **n/e** | **n/e** | Not found | Lineage largely API-fed, not parsed |
| **Alex Solutions** | Automated lineage, mechanism not found | **n/e** | **n/e** | **n/e** | **n/e** | Not found | No mechanism detail retrieved |

Additional cross-cutting inferences for the report writer:
- A buyer needing all four objectives would, on this evidence, have to combine tools or build: (i) a code-scanner engine for depth and history (Manta class), (ii) OpenLineage emission from microservices, Kafka/Flink jobs and feature pipelines, and (iii) a PR-time impact check (Atlan-style action or an MCP/API call in CI).
- Price anchors that are at least semi-public: Atlan ~USD 50K median, Alation ~USD 60K entry / ~USD 141K median, Collibra ~USD 166-197K median, Manta ~CAD 140K per resource unit. All other vendors are quote-only in retrieved material.
- Vendor consolidation is a material risk factor in 2025-2026: Informatica -> Salesforce (Nov 2025), data.world -> ServiceNow (2025), Octopai -> Cloudera (Nov 2024), Zeenea -> HCLSoftware/Actian (Sep 2024), Manta -> IBM (2023), and Ataccama replacing embedded Manta with native scanners plus Rocket.

### Gaps

Open questions that could not be resolved in this session (and why):

1. **Kafka / Flink / microservice / feature-store / ML-model lineage per vendor.** No vendor documentation was retrieved showing native column-level lineage for these hops (the Atlan and IBM queries did not run; others returned nothing). Needs direct doc checks: Atlan Kafka/Confluent and AI-asset connectors, Collibra Kafka and AI model assets, IBM scanner list, Informatica Kafka catalog source, Solidatus connector list.
2. **IBM Manta:** current scanner count and list; whether two-revision comparison (diff) exists in the watsonx.data intelligence edition (reseller says yes, competitor says no); whether file-level incremental analysis ships; scan scheduling and latency; any CI/CD hooks.
3. **Collibra:** whether Edge sync is full or incremental; any lineage history; the definitive 2026 ETL/BI source list (PowerCenter, SSIS, Talend, SSRS); names and granularity of lineage MCP tools; AWS Marketplace and lineage-SKU pricing; the oddly dated "Streaming API lineage flow for GCP" release note.
4. **Informatica:** authoritative CDGC scanner list and column-level coverage for PL/SQL, T-SQL, COBOL, Spark/Python, Kafka; incremental extraction; IPU price points; EDC 10.5.x end-of-support date; post-acquisition roadmap for non-Salesforce estates.
5. **Solidatus:** connector list and depth; whether bi-temporal versioning and diff operate at attribute level; pricing; independent reviews.
6. **Octopai:** native connector list (SSIS, DataStage, Talend, ADF, SSRS/SSAS, Power BI, Tableau, stored-procedure dialects); what the January 2026 "streaming connectors" cover; history/diff; pricing under Cloudera.
7. **Alation:** per-connector stored-procedure and dynamic-SQL handling; lineage versioning; Kafka lineage; current relationship with Manta.
8. **Atlan:** lineage history/diff; GitLab integration docs; whether indirect (join/filter) dependencies are represented; independent confirmation of customer metrics.
9. **data.world / ServiceNow:** official lineage documentation and whether the Manta dependency persists.
10. **Quest:** Smart Data Connector catalogue and prices; incremental/versioning behaviour.
11. **Rocket:** column-level depth for COBOL; scanner count in 2026; incremental and point-in-time mechanics; pricing.
12. **Ataccama:** v17 supported-technology table; stored-procedure coverage; when Manta embedding ended.
13. **Precisely:** Data360 Govern lifecycle status and migration path; connector list for the Data Integrity Suite.
14. **Alex Solutions, Zeenea, Orion:** essentially all mechanism, O2-O4 and pricing detail.
15. **Analyst and independent evidence:** Bloor and BARC lineage reports; full Gartner 2026 MQ placements and the January-vs-November 2026 publication-date conflict; practitioner reviews (Reddit, G2, Peer Insights); any vendor-published or independent MTTD/MTTR figures attributable to lineage.
16. **Method limitation to lift before finalising:** `www.ibm.com`, `productresources.collibra.com` and `www.solidatus.com` (and likely other vendor doc hosts) must be added to the session's allowed network domains for full-page verification, and the web-search budget must be raised or a follow-up session run to close items 1-15.
