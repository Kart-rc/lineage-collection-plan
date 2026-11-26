# Independent market view of data lineage vendors: analysts, consolidation, pricing, practitioner sentiment and outcome evidence (as of 26 November 2026)

**Method and limitations (read first).** Research ran on 26 Nov 2026. Two session constraints shaped the evidence base:

1. `WebFetch` failed for all three hosts tried (apmdigest.com, tei.forrester.com, dataopsleadership.substack.com: not resolvable from this session's network), and per the tool's guidance no further hosts were attempted, so no page was read in full. Every finding below comes from web-search result summaries and snippets. Quotes are as surfaced in snippets and should be re-checked against the page before being printed verbatim in a report.
2. The shared web-search budget for the turn ran out after roughly 70 queries. Several key questions were therefore only partly researched or not researched at all: Reddit / Hacker News practitioner quotes, build-vs-buy accounts, pre-merge breaking-change evidence, migration savings, PRA / OCC / MAS / EU AI Act / DORA primary texts, OpenLineage hyperscaler adoption, Octopai pricing, public-sector contract disclosures. These are listed as gaps, not guessed.

Provenance labels used throughout: **[vendor-claimed]**, **[vendor-commissioned]** (e.g. Forrester TEI), **[survey]** (and who paid), **[marketplace list]** (public AWS/Azure listing), **[buyer-aggregator]** (Vendr / CostBench deal data), **[analyst]**, **[regulator]**, **[practitioner]**, **[secondary]** (third-party summary not checked against the primary). Nothing below is independently measured unless it says so; I found no independently measured outcome data at all.

---

## 1. Analyst coverage 2025-2026: segmentation, leaders, lineage-related criteria, cautions, predictions

### Takeaway
Analysts no longer treat lineage as its own market: it is scored as a capability inside governance platforms (Gartner, Forrester), metadata management (Gartner's revived MQ, Nov 2025), data intelligence platforms (IDC, BARC) and data observability (Gartner Market Guide, Feb 2026, where lineage and impact analysis is a mandatory feature). The same five names recur as leaders (Collibra, Informatica, IBM, Alation, Atlan), but full quadrant placements, strengths and cautions are paywalled and what is public is almost entirely vendor self-reporting.

### Cited Findings

**Gartner Magic Quadrant for Data and Analytics Governance Platforms**
- Gartner has two separate documents in calendar 2026: one published 6 January 2026 and one published 12 November 2026. Vendors label both "2026". — [Gartner abstract, doc 7315430](https://www.gartner.com/en/documents/7315430); [Gartner abstract, doc 8625433](https://www.gartner.com/en/documents/8625433)
- The November 2026 edition evaluates 16 vendors. **[secondary, vendor-hosted]** — [Atlan guide to the Nov 2026 MQ](https://atlan.com/know/gartner/magic-quadrant-for-data-governance-november-2026/)
- An earlier article on the January 2026 edition describes 15 platforms rated. **[secondary]** — [AI, Data & Analytics Network](https://www.aidataanalytics.network/data-governance/news-trends/gartner-rates-15-data-analytics-governance-platforms-in-new-magic-quadrant)
- Atlan: Visionary in the 2025 edition, Leader in the January 2026 edition, and in the November 2026 edition a Leader "for the second time in a row, positioned highest on Ability to Execute" (press release dated 17 Nov 2026). **[vendor-claimed]** — [Atlan, Jan 2026](https://atlan.com/atlan-named-leader-in-gartner-da-governance-magic-quadrant/); [Business Wire via Morningstar, 17 Nov 2026](https://www.morningstar.com/news/business-wire/20261117013330/atlan-named-a-leader-in-the-2026-gartner-magic-quadrant-for-data-and-analytics-governance-platforms-positioned-highest-on-ability-to-execute)
- Collibra: Leader "for the third consecutive year". **[vendor-claimed]** — [Collibra blog](https://collibra.com/blog/collibra-recognized-as-a-leader-for-the-third-consecutive-year-in-the-gartner-magic-quadrant)
- Informatica (now part of Salesforce): Leader "for the third time". **[vendor-claimed]** — [Informatica](https://www.informatica.com/data-governance-magic-quadrant.html)
- IBM: Leader in the 2026 MQ (page title only) and in the 2025 MQ. **[vendor-claimed]** — [IBM 2026](https://www.ibm.com/forms/mkt-report-0d537); [IBM 2025](https://www.ibm.com/forms/mkt-54249)
- Ataccama: Visionary in the January 2026 edition, and describes itself as "the only Visionary" in the 2026 MQ. Its January 2026 post calls that report the "second edition" of this MQ. **[vendor-claimed]** — [Ataccama blog](https://www.ataccama.com/blog/gartner-magic-quadrant-for-data-and-analytics-governance-platforms-2026-explained-what-changed-this-year); [Ataccama analyst page](https://www.ataccama.com/analyst-research/the-2026-gartner-magic-quadrant-for-data-and-analytics-governance-platforms)
- A third-party blog headline groups Collibra, Alation, Microsoft Purview and Informatica in the 2026 MQ; I could not confirm Alation's or Microsoft's quadrant from any primary or vendor source. **[secondary, unverified]** — [Bilytica](https://bilytica.com/blog/gartner-2026-magic-quadrant-data-governance-tools/)
- Gartner's category definition: platforms that help organizations "design and enforce governance policies for data and its derived assets across its life cycle". **[analyst]** — [Gartner abstract](https://www.gartner.com/en/documents/7315430)

**Gartner Magic Quadrant for Metadata Management Solutions (2025)**
- Published November 2025 (3 Nov per Atlan's citation, 19 Nov per IBM's; conflict unresolved). First evaluation of this market since 2020. **[vendor-claimed on dates]** — [Gartner abstract, doc 7195830](https://www.gartner.com/en/documents/7195830); [Informatica via Business Wire, 21 Nov 2025](https://businesswire.com/news/home/20251121159172/en/Informatica-Named-a-Leader-in-the-2025-Gartner-Magic-Quadrant-for-Metadata-Management-Solutions-Report); [IBM](https://www.ibm.com/forms/mkt-54143)
- Gartner's abstract describes the market as undergoing "a significant evolution, shifting from augmented data catalogs to metadata 'anywhere' orchestration platforms". **[analyst]** — [Gartner abstract](https://www.gartner.com/en/documents/7195830)
- Leaders per Atlan's page: Atlan, Alation, Informatica, IBM, Collibra. A third-party summary instead lists Ab Initio, Alation, Atlan, IBM, Informatica (no Collibra). Collibra's placement is therefore unconfirmed. **[vendor-claimed / secondary; conflicting]** — [Atlan](https://atlan.com/gartner-magic-quadrant-for-metadata-management); contradicted by [Spotlight summary](https://research.oz.spotlightar.com/reports/magic-quadrant-metadata-management-solutions-2025/leaders)
- Vendor count conflicts: 12 (Alation) versus 15 (Atlan). Alation says this is its fifth Leader placement. **[vendor-claimed]** — [Alation](https://www.alation.com/blog/alation-gartner-leader-metadata-management-2025/); [Atlan](https://atlan.com/gartner-magic-quadrant-metadata-management-solutions-2025/)
- No placement found for DataHub or Solidatus in this MQ. — search returned nothing; see Gaps.

**Gartner Market Guide for Data Observability Tools (2026)**
- Published 23 February 2026; authors Melody Chien and Michael Simone. **[analyst, via vendor reprint]** — [Gartner abstract, doc 7490153](https://www.gartner.com/en/documents/7490153); [Datadog reprint page](https://www.datadoghq.com/resources/gartner-reprint-data-observability-market-guide/)
- Vendor summaries say Gartner's mandatory features include alerting and triage plus data lineage and impact analysis, and that the defining trend is a move to unified platforms. About 20 representative vendors; Bigeye, Ataccama, Monte Carlo, Datadog and DQLabs all say they are listed. **[secondary, vendor summaries]** — [Monte Carlo commentary](https://www.montecarlodata.com/blog-what-2026-gartner-market-guide-for-data-observability-tools-means-for-your-data-and-ai-team-my-take/); [Bigeye](https://bigeye.com/resources/gartner-market-guide-for-data-observability-tools-2026)
- Gartner's 2025 State of AI-Ready Data Survey, as quoted by Monte Carlo: 53% of data and AI leaders have implemented data observability tools and a further 43% plan to within 18 months. **[survey by Gartner, relayed by a vendor]** — [Monte Carlo commentary](https://www.montecarlodata.com/blog-what-2026-gartner-market-guide-for-data-observability-tools-means-for-your-data-and-ai-team-my-take/)
- An older Gartner projection, relayed by a vendor blog about the 2024 edition: 50% of enterprises implementing distributed data architectures will have adopted data observability tools by 2026. **[analyst prediction, secondhand]** — [Monte Carlo](https://montecarlodata.com/blog-interpreting-the-gartner-data-observability-market-guide)

**Forrester**
- The Forrester Wave: Data Governance Solutions, Q3 2025 evaluated 13 providers on 28 criteria. Forrester's own blog headline: the Wave "Shows That Governance Has Entered The Agentic Era". **[analyst]** — [Forrester blog](https://forrester.com/blogs/the-forrester-wave-data-governance-solutions-q3-2025-shows-that-governance-entered-the-agentic-era); [Forrester report page](https://www.forrester.com/report/the-forrester-wave-tm-data-governance-solutions-q3-2025/RES184107)
- Self-declared Leaders: Collibra, Alation (press release 9 July 2025), Atlan (also "Customer Favorite", highest possible score in 15 criteria). Collibra was separately a Strong Performer in the AI Governance Platforms Wave, Q3 2025. **[vendor-claimed]** — [Collibra](https://www.collibra.com/blog/collibra-named-a-leader-in-the-forrester-wave-data-governance-solutions-q3-2025); [Alation](https://www.alation.com/news-and-press/alation-named-leader-2025-forrester-data-governance-solutions-report/); [Atlan](https://atlan.com/forrester-wave/)
- The Forrester Wave: Enterprise Data Catalogs, Q3 2024 evaluated 12 solutions on 24 criteria, with data lineage an explicit criterion. Atlan and Collibra report Leader status; Atlan reports the highest possible score in Data Lineage. No 2025 or 2026 catalog Wave was found. **[vendor-claimed]** — [Atlan](https://atlan.com/forrester-wave-enterprise-data-catalogs-2024/); [Collibra](https://collibra.com/blog/collibra-a-leader-in-the-forrester-wave-enterprise-data-catalogs-q3-2024); [Forrester report page](https://www.forrester.com/report/the-forrester-wave-tm-enterprise-data-catalogs-q3-2024/RES181073)

**IDC**
- IDC MarketScape: Worldwide Data Intelligence Platform Software 2026 Vendor Assessment (August 2026, Doc #US54118226) covered 15 vendors: 8 Leaders and 7 Major Players. **[secondary]** — [Atlan summary](https://atlan.com/know/data-catalog/idc-marketscape-data-intelligence-platform-software-2026/)
- Vendors claiming Leader: Alation (blog dated 3 Sep 2026), Qlik, Precisely, Snowflake, Collibra. **[vendor-claimed]** — [Alation](https://www.alation.com/blog/idc-marketscape-2026-data-intelligence-leader/); [Qlik](https://www.qlik.com/us/news/company/press-room/press-releases/qlik-named-a-leader-in-the-2026-idc-marketscape-for-worldwide-data-intelligence-platform-software); [Precisely](https://www.precisely.com/press-release/precisely-named-a-leader-in-idc-marketscape-worldwide-data-intelligence-platform-software-2026-vendor-assessment/); [Snowflake](https://www.snowflake.com/en/resources/report/snowflake-named-a-leader-in-the-idc-marketscape--worldwide-data-/); [Collibra](https://www.collibra.com/resources/idc-marketscape-worldwide-data-intelligence-platform-software-2026-vendor-assessment)
- Databricks is a Leader in a separate IDC MarketScape for Unified AI Governance Platforms 2025-2026. **[vendor-claimed]** — [Databricks](https://www.databricks.com/blog/databricks-named-leader-idc-marketscape-worldwide-unified-ai-governance-platforms-2025-2026)

**BARC**
- BARC Score Data Intelligence Platforms, fourth edition, published May 2026, evaluates ten vendors on Portfolio Capabilities and Market Execution. It excludes platform-native catalogs (Databricks Unity Catalog, Snowflake Horizon, Google Dataplex, AWS Glue, IBM Knowledge Catalog, Oracle Data Catalog, Microsoft Purview) as not standalone offerings. BARC's framing: platforms must "not only curate business context, lineage, and policies, but deliver them to models and agents at inference time". **[analyst]** — [BARC, "From Data Catalog to Context Provider for AI Agents"](https://barc.com/news/from-data-catalog-to-context-provider-for-ai-agents/); [BARC product page](https://barc.com/product/barc-score-data-intelligence-platforms)
- The 2025 edition (February 2025) covered Ab Initio, Alation, Alex Solutions, Ataccama, Atlan, Collibra, DataGalaxy, data.world, IBM, Informatica, Microsoft, Precisely, OvalEdge and erwin by Quest. **[analyst]** — [BARC](https://barc.com/news/barc-score-ai-and-automation-propel-data-intelligence-platforms-forward/)

**GigaOm**
- No GigaOm Radar dedicated to data lineage was found for 2025 or 2026. GigaOm's Data Observability Radar treats data lineage as a table stake (a capability every included product must have). **[analyst]** — [GigaOm Radar for Data Observability](https://s.gigaom.com/?p=1017010)
- 2025 GigaOm Radar for Data Catalogs: Cloudera and Databricks each claim "Leader and Outperformer". Positions of Atlan, Alation and Collibra not found. **[vendor-claimed]** — [Cloudera](https://www.cloudera.com/campaign/gigaom-2025-data-catalogs-radar.html); [Databricks awards](https://www.databricks.com/company/awards-and-recognition)

**Gartner predictions and related research**
- 11 March 2026: by 2030, 50% of organizations will use autonomous AI agents to convert governance policies and technical standards into machine-verifiable data contracts. **[analyst prediction]** — [Gartner press release](https://www.gartner.com/en/newsroom/press-releases/2026-03-11-gartner-announces-top-predictions-for-data-and-analytics-in-2026)
- 21 January 2026: by 2028, 50% of organizations will adopt zero-trust data governance as unverified AI-generated data grows; the release recommends active metadata practices to alert when data is stale or needs recertification. **[analyst prediction]** — [Gartner press release](https://www.gartner.com/en/newsroom/press-releases/2026-01-21-gartner-predicts-by-2028-50-percent-of-organizations-will-adopt-zero-trust-data-governance-as-unverified-ai-generated-data-grows)
- 17 June 2025: by 2027, 50% of business decisions will be augmented or automated by AI agents for decision intelligence; the same release says metadata "provides the context, lineage and governance needed to track, verify and manage synthetic data responsibly". **[analyst prediction]** — [Gartner press release](https://www.gartner.com/en/newsroom/press-releases/2025-06-17-gartner-announces-top-data-and-analytics-predictions)
- Per Atlan's reading of Gartner's 2026 Hype Cycles, context graphs and data contracts sit at the Innovation Trigger. **[secondary]** — [Atlan newsletter](https://atlan.com/context-and-chaos/issue/gartner-hype-cycles-2026-nobody-owns-context/)
- A Gartner abstract on data catalogs says they "suffer from a high failure rate" that is often blamed on technology choices but is more often the result of nontechnical issues. **[analyst]** — [Gartner abstract, doc 6828634](https://www.gartner.com/en/documents/6828634)

### Inferences
- The D&A Governance MQ appears to have had three editions in under two years (2025; 6 Jan 2026; 12 Nov 2026). That reading reconciles Collibra's "third consecutive", Informatica's "third time" and Atlan's Visionary, then Leader, then "second time in a row". It is an inference from vendor statements and two Gartner document IDs, not confirmed from Gartner's text.
- Column-level lineage is not a published, separately scored criterion in any of the public summaries. The only explicit lineage criterion I could confirm is in the Forrester Enterprise Data Catalogs Wave (Q3 2024). Buyers who care about element-level depth cannot read it off a quadrant position.
- Analysts structurally under-rank platform-native lineage. BARC excludes Unity Catalog, Horizon, Purview and Dataplex by rule, even though those are where much column-level lineage is captured in practice. A shortlist built only from analyst leaders will omit them.
- Dedicated lineage specialists (Solidatus, Manta before IBM, Octopai before Cloudera) are largely invisible in 2025-2026 analyst rankings. That is consistent with lineage being absorbed into broader platforms.

### Gaps
- Full quadrant placements, strengths and cautions for every Gartner MQ are paywalled; no cautions text was retrievable. Vendor reprint pages could not be fetched in this session.
- Bloor Research data lineage market update: not found.
- Gartner Market Guide for Active Metadata Management: no 2025-2026 edition found; may have been superseded by the Metadata Management MQ. Not confirmed.
- GigaOm Data Observability Radar leaders, and GigaOm Data Catalogs Radar positions for Atlan / Alation / Collibra: not found.
- An often-repeated "by 2026, 30% of organizations will adopt active metadata practices" Gartner figure appeared only on a vendor page and could not be traced to Gartner. — [Atlan](https://atlan.com/gartner-active-metadata-management/)
- Gartner Peer Insights "Voice of the Customer" reports for these markets: not searched.

---

## 2. Market consolidation 2022-2026 and what it implies for lock-in and roadmap risk

### Takeaway
Between late 2024 and late 2026 most independent lineage, catalog and observability specialists were bought by platform vendors that want a metadata "context layer" for AI agents: Octopai (Cloudera), Metaplane (Datadog), data.world (ServiceNow), Informatica (Salesforce), Select Star (Snowflake), Secoda (Atlassian), CastorDoc and SYNQ (Coalesce), Tobiko then dbt Labs (Fivetran), Elementary (Boomi). The remaining independents found in this research are Collibra, Alation, Atlan, DataHub, Solidatus, Monte Carlo, Bigeye, Datafold, Collate and Ataccama; Monte Carlo shows signs of financial stress.

### Cited Findings

**Lineage specialists absorbed**
- Collibra acquired SQLdep, a SaaS automated-lineage provider (press release; year not shown in the snippet). **[vendor-claimed]** — [Collibra pressroom](https://collibra.com/pressroom/collibra-announces-acquisition-of-sqldep); [A-Team Insight](https://a-teaminsight.com/blog/collibra-acquires-sqldep-expands-european-presence)
- Cloudera signed a definitive agreement for Octopai's lineage and catalog platform in November 2024 (deal tracker lists 14 Nov 2024). The product now ships as "Cloudera Octopai Data Lineage" with "more than 60 native integrations". **[vendor-claimed]** — [Cloudera blog](https://www.cloudera.com/blog/business/octopai-acquisition-enhances-metadata-management.html); [SD Times](https://sdtimes.com/cloudera-to-acquire-octopais-platform-to-deliver-trusted-data-across-the-entire-hybrid-cloud-data-estate/); [Mergr](https://mergr.com/transaction/cloudera-acquires-octopai-data-lineage-and-catalog-platform)
- IBM Manta is now sold inside IBM watsonx.data intelligence, which IBM positions as cataloguing, governance and lineage in one platform. — [IBM](https://www.ibm.com/forms/mkt-54143)

**Catalogs absorbed by application and platform vendors**
- ServiceNow announced the data.world acquisition on 7 May 2025 at Knowledge 2025 and closed it in Q3 2025; terms undisclosed; folded into Workflow Data Fabric. — [TechCrunch, 7 May 2025](https://techcrunch.com/2025/05/07/servicenow-acquires-data-world-two-months-after-acquiring-moveworks); [ServiceNow press room](https://www.servicenow.com/de/company/media/press-room/workflow-data-fabric-ai-agents.html)
- Salesforce completed the Informatica acquisition on 18 November 2025 (about $8bn). — [Salesforce press release](https://www.salesforce.com/news/press-releases/2025/11/18/salesforce-completes-acquisition-of-informatica/); [TechRadar](https://www.techradar.com/pro/salesforce-snaps-up-informatica-in-usd8bn-deal-to-boost-ai-tools)
- Snowflake announced a definitive agreement to acquire the Select Star team and technology on 24 November 2025, to extend Horizon Catalog to PostgreSQL, MySQL, Tableau, Power BI, dbt and Airflow for agentic AI (Snowflake Intelligence, Cortex Code). Terms undisclosed. The deal is real; closing date not verified. — [Snowflake blog](https://snowflake.com/en/blog/snowflake-acquire-select-star/); [Benzinga](https://www.benzinga.com/m-a/25/11/49061002/snowflake-acquires-data-startup-select-star-to-boost-its-ai-and-cloud-capabilities)
- Atlassian acquired Secoda (undisclosed price) to support structured data for Rovo AI; one guide dates it December 2025. — [TechTarget](https://www.techtarget.com/searchitoperations/news/366636012/Atlassians-Secoda-acquisition-adds-data-catalog-for-Rovo-AI); [ClickUp guide (date)](https://clickup.com/blog/secoda-alternatives)
- Coalesce bought CastorDoc (AI catalog), then announced SYNQ (observability) on 10 March 2026, rebranded as Coalesce Quality. — [TechTarget](https://www.techtarget.com/data-technologies/news/366621023/Coalesce-acquires-data-catalog-upstart-to-aid-transformation); [Coalesce](https://coalesce.io/company-news/coalesce-announces-acquisition-of-synq-and-launch-of-coalesce-quality/)
- Alation agreed to acquire Numbers Station (agentic AI; raised over $17M). — [TechTarget](https://www.techtarget.com/data-technologies/news/366624026/Alation-boosts-agentic-AI-with-Numbers-Station-acquisition)
- Collibra acquired Raito (data access governance) on 5 June 2025 and Deasy Labs (unstructured data) on 24 July 2025. — [TechCrunch](https://techcrunch.com/2025/06/05/collibra-acquires-data-access-startup-raito/); [Collibra](https://www.collibra.com/company/newsroom/press-releases/collibra-acquires-deasy-labs); [TechTarget](https://www.techtarget.com/data-technologies/news/366627998/Collibras-acquisition-of-Deasy-targets-unstructured-data)

**Transformation layer (where SQL column lineage is computed)**
- Fivetran acquired Tobiko Data (SQLMesh and SQLGlot) on 3 September 2025. — [Business Wire](https://www.businesswire.com/news/home/20250903275106/en/Fivetran-Acquires-Tobiko-Data-to-Power-the-Next-Generation-of-Advanced-AI-Ready-Data-Transformation)
- Fivetran and dbt Labs announced an all-stock merger on 13 October 2025 and closed it on 1 June 2026. George Fraser is CEO, Tristan Handy president. At close they announced dbt Core v2.0 (alpha, Apache 2.0, built on the Fusion engine) and say they serve more than 100,000 data teams. The roughly $600M ARR figure was a pre-close forecast. — [Fivetran press release](https://www.fivetran.com/press/fivetran-dbt-labs-complete-merger-to-create-the-data-infrastructure-for-trusted-ai-agents); [TechTarget](https://www.techtarget.com/data-technologies/news/366643590/Fivetran-DBT-Labs-complete-merger-to-form-data-layer-for-AI); [Business Wire, 13 Oct 2025](https://www.businesswire.com/news/home/20251013172495/en/Fivetran-and-dbt-Labs-Unite-to-Set-the-Standard-for-Open-Data-Infrastructure)
- One analysis notes the combined company now owns ingestion connectors, dbt, SQLMesh and a reverse-ETL tool. **[secondary]** — [datadriven.io](https://datadriven.io/blog/fivetran-and-dbt-labs-merge-what-data-engineers-should-know)

**Observability**
- Datadog acquired Metaplane (which offers column-level lineage) on 23 April 2025. — [TechCrunch](https://techcrunch.com/2025/04/23/datadog-acquires-ai-powered-observability-startup-metaplane); [Datadog](https://datadoghq.com/blog/datadog-acquires-metaplane)
- Snowflake announced a definitive agreement to acquire Observe on 8 January 2026 (telemetry observability, not data lineage). — [Futurum](https://futurumgroup.com/?p=85406)
- Boomi acquired Elementary Data in October 2026 (undisclosed). Elementary includes column-level lineage, a catalog and an MCP server exposing context to AI agents. — [Constellation Research](https://www.constellationr.com/insights/news/boomi-acquires-elementary-data-adds-data-observability-quality-governance-layer); [Tribune, 27 Oct 2026](https://tribune.net.ph/2026/10/27/boomi-acquires-elementary-data)
- Monte Carlo: last priced round was a $135M Series D. Blind's layoff tracker logs 80 cuts (about 29.6% of staff) on 17 March 2026 and TrueUp reports a similar ~30%; TrueUp also shows an estimated $0.6B secondary valuation in May 2026 against $1.6B in May 2022. All are third-party trackers, not company statements. Monte Carlo launched Agent Observability in March 2026. **[third-party trackers, unverified]** — [Blind](https://www.teamblind.com/layoffs/company/monte-carlo-data); [TrueUp](https://trueup.io/co/monte-carlo); [APMdigest (Series D)](https://www.apmdigest.com/monte-carlo-raises-135m-in-series-d-funding)

**Independents: funding and positioning**
- DataHub: Acryl Data renamed itself DataHub and closed a $35M Series B led by Bessemer on 21 May 2025 (total about $65M; other investors include 8VC and In-Q-Tel). Claims 3,000+ organizations including Apple, Netflix, Pinterest, Slack, Optum, Chime. **[vendor-claimed on adoption]** — [SiliconANGLE](https://siliconangle.com/?p=697187); [Axios](https://www.axios.com/pro/enterprise-software-deals/2025/05/21/exclusive-datahub-raises-35m-in-bessemer-led-series-b)
- Atlan: latest round found is a $105M Series C on 8 May 2024 at a $750M valuation (GIC, Meritech). No 2025-2026 round found. — [TechCrunch](https://techcrunch.com/2024/05/08/atlan-scores-105m-for-its-data-control-plane-as-llms-boost-importance-of-data)
- Solidatus: £5M from Salica Investments; version 2026.3 (6 July 2026) added MCP support and bring-your-own-LLM; chosen as a Microsoft Purview lineage integration partner. **[vendor-claimed]** — [Solidatus 2026.3](https://www.solidatus.com/news/solidatus-launches-2026-3-product-update/); [Solidatus funding](https://www.solidatus.com/news/solidatus-secures-5-million-backing-from-salica-investments/); [Solidatus for Purview](https://www.solidatus.com/product/solidatus-for-microsoft-purview/)

**Platform catalog moves**
- Databricks agreed to buy Tabular (the Apache Iceberg creators) on 4 June 2024 for a reported $1-2bn. Snowflake had announced the open Polaris Catalog one day earlier, promising to open-source it within 90 days. Databricks subsequently open-sourced Unity Catalog. (Older than the 2025-2026 window; context only.) — [The Register, 5 Jun 2024](https://www.theregister.com/2024/06/05/databricks_buys_tabular_for_1b/); [Blocks & Files](https://blocksandfiles.com/2024/06/05/databricks-buys-tabular-to-win-the-iceberg-war/); [InfoWorld](https://www.infoworld.com/article/2337390/databricks-to-acquire-storage-platform-maker-tabular.html)

**Commentary on consequences**
- Kai Waehner (Global Field CTO at Confluent, so not neutral), 18 May 2026: platform-native tools such as Snowflake Horizon, Databricks Unity Catalog and AWS DataZone work well inside their own platforms, but no single-platform lineage tool can deliver the cross-system view a regulatory report needs; he argues for a catalog layer that "sits above all platforms, integrates with all of them, and is owned by none of them". **[practitioner/vendor-affiliated opinion]** — [kai-waehner.de](https://www.kai-waehner.de/blog/2026/05/18/beyond-enterprise-data-lineage-the-case-for-a-platform-independent-data-catalog/)
- One 2026 commentator reports that Secoda's and Select Star's public sites looked unchanged a year after acquisition apart from an ownership banner, with no visible new releases, and that Secoda's standalone roadmap is consolidating into Atlassian's platform. This is a single author's observation surfaced in search; I could not confirm which page it came from. **[secondary, unverified]** — candidates: [toolsfordata.com market guide 2026](https://toolsfordata.com/guides/data-governance-tool/); [nidhivichare.com "The Other Catalog War"](https://www.nidhivichare.com/blog/catalog-wars-part-3)

### Inferences
- Roadmap risk is concrete for four products the brief names: Select Star (being folded into Snowflake Horizon), Secoda (into Atlassian Rovo), Octopai (now a Cloudera-branded product) and Informatica (a Salesforce unit since Nov 2025). A buyer who wants cross-platform, vendor-neutral lineage should assume each acquirer will prioritize its own platform's coverage.
- The acquirers' stated rationale is nearly identical across deals: give AI agents governed context. Lineage is being repositioned from a governance artefact to an input for agents, which is likely where product investment goes in 2027.
- Open-source cores reduce lock-in less than they appear to once ownership concentrates. SQLGlot (the parser behind much open-source column lineage), SQLMesh and dbt are now controlled by one company. The Apache 2.0 licence on dbt Core v2.0 mitigates this, but the roadmap sits with a single vendor.
- Among remaining independents, the evidence of financial stress is specific to Monte Carlo (tracker-reported layoffs, lower secondary valuation). I found no comparable signal for Collibra, Alation, Atlan, DataHub or Solidatus, but I also found no 2026 funding data for them, so absence of signal is weak evidence.

### Gaps
- Not verified in this session (the following come from my background knowledge and need a source before use): IBM-Manta announced October 2023; Collibra-SQLdep was 2019; dbt Labs-SDF January 2025; Coalesce-CastorDoc March 2025; Alation-Numbers Station May 2025; Bigeye-Data Advantage Group 2023; Unity Catalog open-sourced June 2024; Snowflake-Crunchy Data June 2025; IBM-Databand 2022; Teradata-Stemma 2023; HCLSoftware-Zeenea 2024.
- Reported but unverified 2026 deals surfaced in one secondary search summary: Collibra buying trail ML (October 2026, AI compliance), SAP agreeing to buy Reltio, ServiceNow closing Veza, Snowflake agreeing to buy Natoma (an MCP gateway). I could not confirm any against a primary announcement.
- Whether the Snowflake-Select Star deal closed, and what happened to existing Select Star customers on non-Snowflake stacks: not found.
- Apache Polaris graduation status, and any 2026 lineage-specific features in open Unity Catalog or Polaris: not found.
- Collibra, Alation, Bigeye, Datafold, Sifflet, Anomalo ownership changes in 2026: none found, but the search was shallow.

---

## 3. Pricing evidence: what buyers actually pay

### Takeaway
Public pricing exists for only a few products, and the best evidence is Vendr deal data plus AWS Marketplace list prices. Enterprise governance suites land around $170K-$200K per year at the median (Collibra) with long tails above $300K (Alation), while modern catalogs and observability tools have medians of roughly $36K-$54K (Select Star, Atlan, Monte Carlo) and $25K (Bigeye). No public price was found for Solidatus, Octopai, Secoda, Datafold, Collate or IBM Manta list.

### Cited Findings

**Collibra**
- Vendr marketplace: median $197,142 per year, range $174,740 to $225,360. Vendr buyer guide: average about $166,000 across 5 deals. CostBench labels the Vendr sample n=6, "limited data". **[buyer-aggregator; tiny sample]** — [Vendr marketplace](https://www.vendr.com/marketplace/collibra); [Vendr buyer guide](https://vendr.com/buyer-guides/collibra); [CostBench](https://www.costbench.com/software/data-catalog/collibra/)
- AWS Marketplace: Collibra Cloud Platform 12-month contract listed at $170,000. **[marketplace list]** — [AWS Marketplace](https://aws.amazon.com/marketplace/pp/prodview-6gqg3yc2e2rsu)
- G2 lists Collibra's time to implement as 6 months. **[review-site aggregate]** — [G2](https://www.g2.com/products/collibra)

**Alation**
- AWS Marketplace: Alation Data Catalog from $60,000 for 12 months; connectors are priced separately (examples: Microsoft Purview connector $28,800 per 12 months; Azure Data Explorer BI connector $30,000). **[marketplace list]** — [AWS Marketplace](https://aws.amazon.com/marketplace/pp/prodview-ylge6fq43dtg6)
- Vendr marketplace: range $76,044 to $302,618 per year. A separate figure of a $580,725 median based on only 4 deals also circulates; treat as an outlier. **[buyer-aggregator; tiny sample]** — [Vendr](https://www.vendr.com/marketplace/alation); [CostBench comparison](https://www.costbench.com/compare/alation-vs-atlan/)
- A competitor-authored guide says typical deployments start around $198,000 per year for 25 Creator seats. **[competitor-authored, low reliability]** — [Atlan on Alation pricing](https://atlan.com/alation-pricing/)

**Atlan**
- Vendr marketplace: median $44,087 (26 purchases), range about $24K to $109K. Vendr buyer guide: $45,900 (29 purchases), range about $28K to $132K. CostBench citing Vendr: $49,764 (43 purchases). **[buyer-aggregator]** — [Vendr marketplace](https://vendr.com/marketplace/atlan); [Vendr buyer guide](https://vendr.com/buyer-guides/atlan); [CostBench](https://www.costbench.com/software/data-catalog/atlan/)
- AWS Marketplace: 12-month subscription starting at $100,000. **[marketplace list]** — [AWS Marketplace](https://aws.amazon.com/marketplace/pp/prodview-4qh23e5eiqwow)

**Informatica (Cloud Data Governance and Catalog)**
- Priced by consumption in Informatica Processing Units (IPU). A summary of the August 2026 rate card gives: catalog 0.83 IPU per 100,000 daily assets stored (0.067 above 500,000 assets); governance 0.95 IPU per 1,000 daily assets stored; metadata scanner 0.32 IPU per compute-unit hour. No public dollar price per IPU. **[rate card via secondary]** — [Salesforce-hosted IPU rate card](https://www.salesforce.com/en-us/wp-content/uploads/sites/4/documents/ipu-rate-card.pdf); [Dawiso summary](https://www.dawiso.com/glossary/informatica-pricing)
- UK G-Cloud 15 pricing document (dated 29 Jan 2026) lists "Catalog, Governance & Marketplace (IDMC)" at £53,873.92 per year. **[public-sector list price]** — [UK Digital Marketplace PDF](https://assets.applytosupply.digitalmarketplace.service.gov.uk/g-cloud-15/documents/703188/592589319296837-pricing-document-2026-01-29-1612.pdf)
- A competitor-authored guide collects third-party estimates of about $100,000 to over $500,000 per year. **[competitor-authored, low reliability]** — [Atlan on Informatica pricing](https://atlan.com/informatica/data-catalog-pricing/)

**IBM Manta Data Lineage / watsonx.data intelligence**
- Metric is the resource unit (RU): 1 RU equals 1 data source definition or 5,000 database tables; views and deduced tables are not counted; billing uses the monthly peak; each data-source-and-scanner combination counts as one RU. **[vendor documentation]** — [IBM plans doc](https://www.ibm.com/docs/en/DSXDOC/wsj/getting-started/wxdintell-plans.html); [IBM support](https://www.ibm.com/support/pages/ibm-manta-data-lineage)
- A CDW reseller listing shows "MANTA Automated Data Lineage for IBM Cloud Pak for Data, subscription license, 1 resource unit" at $87,821.99. This is a reseller price for the Cloud Pak edition and may use a different unit definition. **[reseller list]** — [CDW](https://cdw.com/product/manta-automated-data-lineage-for-ibm-cloud-pak-for-data-subscription-lice/7395092)
- No public IBM list price per lineage RU; AWS Marketplace says contact IBM sales. — [AWS Marketplace](https://aws.amazon.com/marketplace/pp/prodview-4lt7554c34ecs)

**Monte Carlo**
- Vendr buyer guide: average contract $48,056 across 26 deals, minimum $7,500, maximum $120,000, average savings 16.98%. Vendr marketplace: median $53,688 across 54 purchases, range $12,970 to $112,520. **[buyer-aggregator]** — [Vendr buyer guide](https://vendr.com/buyer-guides/monte-carlo); [Vendr marketplace](https://www.vendr.com/marketplace/monte-carlo)
- AWS Marketplace shows a sample 12-month contract of $50,000 in Monte Carlo credits. **[marketplace list]** — [AWS Marketplace](https://aws.amazon.com/marketplace/pp/prodview-hikicsfohm3gg)
- Monte Carlo's own Scale tier is usage-based; a snippet shows $0.50 per table per day (verify on the order form). **[vendor-published; snippet only]** — [Monte Carlo Scale order form](https://montecarlodata.com/request-for-pricing/scale-order-form)
- A benchmark site puts entry-level enterprise ACV near $120,000 per year with a median 18% off list. **[secondary aggregator, unverified method]** — [VendorBenchmark](https://vendorbenchmark.com/vendors/monte-carlo-data-pricing)
- The vendor-commissioned Forrester TEI (April 2025) models $3.07M present-value benefits against roughly $0.67M present-value costs over three years (derived: benefits minus the $2.40M NPV). **[vendor-commissioned; cost figure derived by me]** — [Forrester TEI](https://tei.forrester.com/go/montecarlo/dataaiobservabilityplatform)

**Bigeye**
- Vendr: median $25,000 per year across 10 purchases, range $15,000 to $25,000. **[buyer-aggregator; small sample]** — [Vendr](https://vendr.com/marketplace/bigeye)
- AWS Marketplace private-offer listings show a $75,000 "Lineage Enterprise Starter Package" and a $50,000 "AI Insights" listing. **[marketplace list; snippet only]** — [AWS Marketplace listing](https://aws.amazon.com/marketplace/pp/prodview-fvnvwulb6kfbw)

**Select Star (now being acquired by Snowflake)**
- Vendr-based median $36,000 per year across 13 purchases; 12-month minimum; aggregator per-user prices conflict by about 3x. **[buyer-aggregator; small sample]** — [CostBench](https://costbench.com/software/data-catalog/select-star/)

**DataHub Cloud and Collate**
- DataHub Cloud is quote-based. Third-party pages say its AWS Marketplace listing shows $75,000 per 12-month contract for up to 20 monthly active users, with entry around $60,000. I could not open the listing itself. **[secondary, partly competitor-authored]** — [Atlan on DataHub pricing](https://atlan.com/know/ai-agent/context-layer/datahub-pricing/); [Dawiso](https://dawiso.com/glossary/datahub-pricing.md)
- Collate (managed OpenMetadata): custom pricing via sales or AWS Marketplace private offer; bring-your-own-cloud costs extra. OpenMetadata itself is Apache 2.0 with no licence fee. **[vendor-published]** — [Collate pricing](https://www.getcollate.io/pricing); [Dawiso](https://dawiso.com/glossary/openmetadata-pricing)

**No public price found**
- Solidatus: AWS and Azure Marketplace listings route to sales. — [AWS Marketplace](https://aws.amazon.com/marketplace/pp/prodview-hgwtagukiojri)
- Datafold: Vendr states it has no pricing data; custom pricing. — [Vendr buyer guide](https://vendr.com/buyer-guides/datafold)
- Secoda: sales-led; a "$9 per user per month" figure on one directory conflicts with other sources and looks stale. — [TrustRadius](https://www.trustradius.com/products/secoda/pricing); [SoftwareSuggest](https://www.softwaresuggest.com/secoda/pricing)

**Total-cost signals from buyers**
- A PeerSpot reviewer (Senior Consultant at Infosys) reports that some customers moved away from Collibra Lineage after a couple of years because the cost-benefit did not look favourable. **[practitioner review]** — [PeerSpot, Collibra Lineage pros and cons](https://peerspot.com/products/collibra-lineage-pros-and-cons)
- G2 reviewers of IBM watsonx.data intelligence flag extra licensing and ongoing costs and setup that needs specialized expertise. **[practitioner reviews, aggregated]** — [G2](https://www.g2.com/products/ibm-watsonx-data-intelligence/reviews)

### Inferences
- Vendr medians skew to mid-market buyers who use a procurement intermediary. Large regulated enterprises almost certainly pay several multiples of these medians for Collibra, Informatica, IBM and Alation once connectors, lineage add-ons and services are included. I have no direct evidence of bank-scale contract values.
- Pricing metrics differ in ways that matter for element-level lineage at scale: IBM charges per data source and per 5,000 tables; Informatica per stored asset and scanner compute hour; Monte Carlo per monitored table per day; Alation per seat plus per connector; Atlan and Collibra by negotiated platform tiers. Estates with many sources and many columns will be penalised differently by each.
- Lineage is frequently a separately priced add-on (Alation connectors on AWS Marketplace, Bigeye's $75K lineage package, Collibra Lineage as a distinct PeerSpot product), so a headline catalog price understates the cost of column-level coverage.

### Gaps
- Octopai pricing: not researched before the search budget ran out. Not found.
- Public-sector contract award values (USAspending, UK Contracts Finder, TED) for any of these vendors: not researched, apart from the one UK G-Cloud list price.
- Reddit / Blind pricing anecdotes: not retrievable.
- Implementation and services cost as a share of licence: not found from an independent source.
- Azure Marketplace and Snowflake Marketplace listings: not found beyond Solidatus's contact-sales listing.

---

## 4. Practitioner sentiment on column-level lineage

### Takeaway
The independent evidence I could reach is thin and mostly from blogs and review sites, not Reddit or Hacker News. It points the same way: column-level lineage from SQL parsing is strong on standard warehouse SQL and weak on stored procedures, dynamic SQL and non-SQL code; large lineage graphs go unused because they are hard to read; and some buyers drop paid lineage after two or so years on cost-benefit grounds.

### Cited Findings

**Sceptical practitioner voices**
- Hugo Lu (CEO of Orchestra, so vendor-affiliated), 18 December 2023 (pre-2024, flagged): "Column-level lineage, IMO one of the biggest data fads of the tech boom, is out: AI is in." He argues that neither dbt test output nor column-level lineage showed the root cause in his example, while an LLM explained "exactly what was going wrong, and where". The same piece concedes a counter-example where column lineage makes a null-join bug quick to debug. **[practitioner/vendor opinion]** — [Orchestra blog](https://getorchestra.io/blog/column-lineage-is-out-ai-is-in); [Substack copy](https://dataopsleadership.substack.com/p/column-level-lineage-is-out-ai-is)
- Same author, "Unpopular Opinion: Column-Level Lineage is not a feature you need": notes people mean different things by the term. **[practitioner/vendor opinion]** — [Substack](https://dataopsleadership.substack.com/p/unpopular-opinion-column-level-lineage)
- A practitioner newsletter surfaced in search says many data teams do not use dbt docs or lineage in practice because it is hard to make sense of a thousand nodes on a graph. Exact attribution not confirmed (paraphrase, not a quote). **[practitioner; attribution unconfirmed]** — candidates: [David Jayatillake, "Column Level Lineage"](https://davidsj.substack.com/p/column-level-lineage); [Sung Won Chung, "Going faster is the greatest UX"](https://sungwc.substack.com/p/going-faster-is-the-greatest-ux)

**Accuracy and coverage gaps**
- dbt's own documentation: column-level lineage "reflects the lineage from select statements in models' SQL code" and does not reflect other usage such as joins and filters. **[vendor documentation of a limitation]** — [dbt docs](https://docs.getdbt.com/docs/explore/column-level-lineage)
- A SQL-parser vendor's blog says most SQL lineage tools silently skip stored procedures, breaking on IF/ELSE branches, loops, exception handlers, cursors and dynamic SQL construction. **[vendor blog, self-interested]** — [Gudu / dpriver](https://www.dpriver.com/blog/?p=3177)
- A September 2026 engineering post warns that a SQL parser can produce a plausible lineage graph from a query that never ran, and recommends validating parsed lineage against execution logs. Dynamic SQL that resolves object names only at runtime is named as a cause of missing lineage. **[practitioner blog]** — [OneUptime, 8 Sep 2026](https://oneuptime.com/blog/post/2026-09-08-validate-sql-derived-lineage-production/markdown)
- Academic: an arXiv paper (May 2025) states that existing tools "often fail to accurately infer column lineage due to the absence of metadata". **[peer-review-track research]** — [arXiv 2505.23133](https://arxiv.org/html/2505.23133v1)
- IBM's known-issues page for Manta lineage inside Knowledge Catalog lists incomplete business lineage for ETL-job and BI-report lineage imports, DataStage stages missing from technical lineage graphs, and dummy assets for some S3 files. **[vendor documentation of limitations]** — [IBM docs](https://www.ibm.com/docs/SSNFH6_5.4.x/wsj/catalog/known-issues-wkcop.html)
- Dataedo states its SQL Server procedure and function lineage depends on parser-supported syntax. **[vendor documentation]** — [Dataedo](https://dataedo.com/kb/databases/sql-server/automatic-data-lineage-in-sql-server)

**Review-site sentiment**
- Collibra Lineage on PeerSpot: capturing lineage gets awkward when the stack spans several tools; "lineage generation needs improvement"; some customers left after a couple of years on cost-benefit. Other reviewers found it faster than manual methods or Informatica and praised the visualisation. **[practitioner reviews]** — [PeerSpot](https://peerspot.com/products/collibra-lineage-pros-and-cons); [PeerSpot reviews](https://www.peerspot.com/products/collibra-lineage-reviews/page-2)
- Collibra on G2: steep learning curve, complex initial setup, 6-month time to implement; one reviewer finds business and technical lineage hard to tell apart. **[practitioner reviews, aggregated]** — [G2](https://www.g2.com/products/collibra)
- IBM watsonx.data intelligence (includes Manta) on G2: complex implementation requiring specialized expertise; cost concerns. Gartner Peer Insights shows IBM at 4.2 overall and 4.4 for product capabilities in metadata management (review dated April 2026). Capterra shows 12 Manta reviews with ease of use at 3.7, its lowest sub-score. **[practitioner reviews, aggregated]** — [G2](https://www.g2.com/products/ibm-watsonx-data-intelligence/reviews); [Gartner Peer Insights](https://www.gartner.com/reviews/market/metadata-management-solutions/vendor/ibm); [Capterra](https://www.capterra.com/p/145178/Manta-Flow/reviews/)

**Adoption failure**
- Gartner: data catalogs "suffer from a high failure rate" more often caused by nontechnical issues than by technology choice. **[analyst]** — [Gartner abstract](https://www.gartner.com/en/documents/6828634)
- A catalog vendor describes projects losing momentum after kickoff until the catalog becomes "shelfware". **[vendor blog]** — [Dataedo](https://dataedo.com/blog/why-data-catalog-projects-fail)

### Inferences
- The gap list in the brief (stored procedures, dynamic SQL, Python/Spark, BI, streaming, application code) is confirmed only for stored procedures and dynamic SQL by the sources reached. Python/Spark, streaming and application-code gaps are widely asserted but I retrieved no attributable practitioner source for them in this session.
- The sharpest critique is not that column lineage is inaccurate but that it is rarely the fastest route to a root cause and that the graph is unreadable at scale. That argues for consuming lineage through impact-analysis checks and agents, not through a graph UI.
- Review-site scores for the incumbents are respectable (4.2 and above) while written complaints concentrate on setup effort and cost. Lineage programmes appear to fail on effort and adoption more than on parser accuracy.

### Gaps
- Reddit r/dataengineering and Hacker News: four differently phrased searches returned no thread content. No attributable Reddit or HN quotes were obtained. This is the largest gap against the brief.
- Benn Stancil, Chad Sanderson, Seattle Data Guy, Data Engineering Weekly: no relevant posts surfaced.
- Implementation-time and total-cost anecdotes beyond G2's 6-month Collibra figure: not found.
- Independent benchmarks of column-lineage accuracy across vendors: none found.

---

## 5. Quantified outcome evidence for the four buyer objectives

### Takeaway
Every quantified outcome figure found is vendor-claimed, vendor-commissioned or from a vendor-funded survey; none is independently measured. Evidence exists only for the incident detection and resolution objective (Monte Carlo's Wakefield surveys and Forrester TEI). For baseline lineage, incremental lineage and pre-merge impact analysis I found no quantified outcome evidence at all in this session.

### Cited Findings

**(a) Incident detection and resolution**
- Monte Carlo / Wakefield Research 2022 survey: about 300 data professionals, fielded 28 April to 11 May 2022 (pre-2024, flagged). Average of nearly 61 data incidents per month, each taking an average 13 hours to identify and resolve (793 hours per month); 75% take four or more hours to detect an incident; about half said nine hours on average to resolve; respondents report spending 40% of their time evaluating or checking data quality. **[survey, vendor-funded, self-reported]** — [Business Wire, 9 Aug 2022](https://www.businesswire.com/news/home/20220809005223/en); [BigDATAwire](https://www.hpcwire.com/bigdatawire/2022/08/12/monte-carlo-survey-finds-data-engineers-spend-40-of-their-workday-on-bad-data/); [TDWI](https://tdwi.org/articles/2022/08/09/data-engineers-and-bad-data-survey.aspx)
- Monte Carlo / Wakefield 2023 survey: 200 data professionals, March 2023 (pre-2024, flagged). 74% said business stakeholders identify data issues first "all or most of the time", up from 47% in 2022; monthly incidents 67, up from 59; share of revenue impacted 31%, up from 26%; data downtime up 1.89x year over year. **[survey, vendor-funded, self-reported]** — [APMdigest](https://apmdigest.com/data-downtime); [VentureBeat](https://venturebeat.com/data-infrastructure/data-downtime-almost-doubles-as-professionals-struggle-with-quality-issues-survey-finds/); [Monte Carlo](https://info.montecarlodata.com/state-of-data-quality-2023/)
- Internal inconsistency: the 2022 release says "nearly 61" incidents per month; the 2023 release restates 2022 as 59. — [Business Wire 2022](https://www.businesswire.com/news/home/20220809005223/en) versus [APMdigest 2023](https://apmdigest.com/data-downtime)
- Forrester Total Economic Impact of Monte Carlo's Data + AI Observability Platform (April 2025): 358% ROI, $3.07M present-value benefits, $2.40M NPV, payback under six months, for a composite organization built from interviews with eight decision-makers at six customers. Also models 2.5% savings on warehouse compute and storage. Commissioned by Monte Carlo. No downtime, MTTD or MTTR reduction percentage was visible in the snippets. **[vendor-commissioned]** — [Forrester TEI](https://tei.forrester.com/go/montecarlo/dataaiobservabilityplatform)
- Adoption context: Gartner's 2025 State of AI-Ready Data Survey reports 53% have implemented data observability tools (relayed by Monte Carlo). **[survey by analyst, relayed by vendor]** — [Monte Carlo](https://www.montecarlodata.com/blog-what-2026-gartner-market-guide-for-data-observability-tools-means-for-your-data-and-ai-team-my-take/)

**Other Forrester TEI studies**
- Alation: 364% ROI from a 2019 Forrester TEI based on seven customers (pre-2024, flagged; commissioned by Alation). **[vendor-commissioned, stale]** — [Alation press release, Oct 2019](https://www.alation.com/news-and-press/alation-data-catalog-delivers-364-return-on-investment-according-to-total-economic-impact-study/)
- Collibra, Atlan, Informatica: no Forrester TEI found for 2024-2026. — search returned none.
- Nucleus Research published a 2026 Data Governance Technology Value Matrix (contents not retrieved). — [Nucleus Research](https://nucleusresearch.com/?p=40285)

**(d) Regulatory lineage drivers**
- ECB Guide on effective risk data aggregation and risk reporting (May 2024) is the clearest regulatory driver for attribute-level lineage; see section 7. **[regulator]** — [ECB guide PDF](https://www.ssm.europa.eu/ecb/pub/pdf/ssm.supervisory_guides240503_riskreporting.en.pdf)

### Inferences
- The widely repeated Monte Carlo statistics measure the problem (how long incidents take, who finds them first), not the effect of lineage or observability on it. They are useful for sizing a baseline, not as evidence that a tool reduces MTTD or MTTR.
- Reliability of the Wakefield figures is low to medium: small samples (200-300), self-reported estimates, funded by the vendor selling the remedy, and the restated 2022 baseline (61 versus 59) shows the series is not stable. They are also now three to four years old.
- TEI studies are modelled composites from six or seven hand-picked customers; ROI percentages (358%, 364%) should be treated as marketing, although the cost side of a TEI is a useful sanity check on contract size.
- No evidence found isolates lineage from the rest of an observability or catalog product. Any MTTR claim attributable specifically to column-level lineage would have to come from a buyer's own before-and-after measurement.

### Gaps
- (a) Named-customer case studies with MTTD/MTTR before and after: not researched before the budget ran out.
- (b) Breaking changes caught pre-merge (Datafold, dbt, Recce, SQLMesh, Foundational, Gable case studies): not researched. Not found.
- (c) Migration or impact-analysis effort saved: not researched. Not found.
- (d) GDPR, EU AI Act and DORA as quantified lineage drivers: not researched. Not found.
- Monte Carlo's 2024-2026 survey editions, if any: not found.
- The Monte Carlo TEI's specific downtime-reduction and labour-saving line items: page could not be fetched.

---

## 6. Build versus buy evidence

### Takeaway
Not answered. The search budget ran out before this question was researched; only incidental pointers were collected.

### Cited Findings
- DataHub (open source) claims adoption by over 3,000 organizations, naming Apple, Chime, Foursquare, Netflix, Optum, Pinterest and Slack. **[vendor-claimed]** — [SiliconANGLE, 21 May 2025](https://siliconangle.com/?p=697187)
- Engineering write-ups of in-house lineage exist and were surfaced but not read: Slack ("Data Lineage at Slack") and Yelp ("Spark Data Lineage", August 2022, pre-2024). **[practitioner; contents not retrieved]** — [Slack Engineering](https://slack.engineering/data-lineage-at-slack/); [Yelp Engineering](https://engineeringblog.yelp.com/2022/08/spark-data-lineage.html)
- Spline's Spark lineage parsing had gaps for unsupported commands that had to be filled per customer, per a vendor write-up. **[vendor blog]** — [Monte Carlo, "Building Spark lineage for data lakes"](https://montecarlodata.com/blog-building-spark-lineage-for-data-lakes)
- A competitor-authored total-cost comparison of open-source versus commercial catalogs exists (not read; treat as advocacy). **[competitor-authored]** — [Atlan](https://atlan.com/know/data-catalog/open-source-vs-commercial-data-catalog-total-cost-of-ownership/)

### Inferences
- None that the evidence supports.

### Gaps
- Published 2023-2026 accounts of bought-then-built or built-then-bought lineage: not found (not researched).
- Team sizes, timelines and costs for in-house lineage platforms: not found.
- Scale numbers for OpenMetadata and OpenLineage / Marquez deployments: not found.

---

## 7. Regulated-industry angle (banking and card payments)

### Takeaway
The ECB's May 2024 RDARR guide is the firmest regulatory statement found: it expects complete, current lineage at data-attribute level from capture to final report, including manual steps, and banks describe that as costly. Evidence on PRA, OCC, MAS, the EU AI Act and on which vendors banks use was not obtained.

### Cited Findings
- The ECB published its Guide on effective risk data aggregation and risk reporting in May 2024, framed as minimum supervisory expectations and prerequisites that "are not necessarily sufficient" for sound RDARR, to give supervised banks a common reference point. **[regulator]** — [ECB guide PDF](https://www.ssm.europa.eu/ecb/pub/pdf/ssm.supervisory_guides240503_riskreporting.en.pdf); [Capco summary](https://www.capco.com/intelligence/capco-intelligence/ecb-final-guidelines)
- As relayed by secondary sources, the guide expects "complete and up-to-date data lineage at the data attribute level - starting from data capture to final reporting", covering functional and technical lineage at attribute granularity and including manual steps. Wording is via secondary sources and should be checked against the PDF. **[regulator, via secondary]** — [Solidatus summary of ECB expectations](https://www.solidatus.com/blog/detailed-expectations-around-data-lineage-and-bcbs-239-from-the-european-central-bank-ecb/); [Deloitte](https://www.deloitte.com/fi/fi/services/consulting/perspectives/the-new-frontiers-of-data-lineage-in-banking.html)
- The guide covers seven areas including management-body responsibilities, scope of application, data governance, integrated data architecture and data quality management. **[secondary]** — [EDM Council / Solidatus webinar deck, Feb 2025](https://edmcouncil.org/wp-content/uploads/2025/02/EDMWebinar_Solidatus_02-26-FINAL-Presentation.pdf)
- The ECB judged progress by significant institutions to be generally insufficient and refined the guide using an on-site inspection campaign; a supervisory newsletter of 19 February 2025 follows up. **[regulator]** — [ECB Supervision Newsletter, 19 Feb 2025](https://www.bankingsupervision.europa.eu/press/publications/newsletter/2025/html/ssm.nl250219.en.html)
- Industry describes attribute-level lineage as costly and complex, needing investment in technology, tools and skills. **[vendor/industry deck]** — [EDM Council / Solidatus webinar deck](https://edmcouncil.org/wp-content/uploads/2025/02/EDMWebinar_Solidatus_02-26-FINAL-Presentation.pdf)
- The Association of German Banks published a 2026 position paper on BCBS 239 / RDARR arguing implementation can be phased and risk-based because the guide allows flexibility. File name is dated 4 March 2026; one search summary said May 2026. **[industry body]** — [Bankenverband position paper](https://bankenverband.de/sites/default/files/medien/3/dokumente/2026-03-04-bdb_position-paper_bcbs-239_rdarr.pdf)
- Further consultancy analyses exist (not read): Oliver Wyman (July 2024), Deloitte BCBS 239 Benchmark Survey 2024, EY on BCBS 239 in 2025, Crisil. — [Oliver Wyman](https://www.oliverwyman.com/our-expertise/insights/2024/jul/data-management-risk-reporting-challenges-eu-banks-bcbs239.html); [Deloitte survey PDF](https://www2.deloitte.com/content/dam/Deloitte/de/Documents/financial-services/Deloitte-BCBS239-Benchmark-Survey-2024.pdf); [EY](https://www.ey.com/en_nl/industries/banking-capital-markets/why-bcbs-239-compliance-is-essential-in-2025)
- Vendor positioning for banking lineage: Solidatus markets directly against the ECB expectations and is a Microsoft Purview lineage partner. **[vendor-claimed]** — [Solidatus](https://www.solidatus.com/product/solidatus-for-microsoft-purview/)

### Inferences
- "Element-level lineage" in the buyer's sense maps directly onto the ECB's "data attribute level" language. For any euro-area significant institution this is a supervisory expectation, not a nice-to-have, and it explicitly includes manual steps that parser-based tools cannot see.
- Because the ECB wants both functional (business) and technical lineage at attribute level, tools that only produce technical column lineage from SQL will not satisfy it alone; a business-lineage or modelling layer is also needed.

### Gaps
- Not verified in this session (background knowledge, needs a source): BCBS 239 was issued January 2013 with 14 principles; the Basel Committee's November 2023 progress report found only 2 of 31 assessed banks fully compliant.
- Not verified (background knowledge, important nuance for the brief): under EU AI Act Annex III, credit scoring of natural persons is high-risk, but AI systems used to detect financial fraud are expressly carved out of that item. If correct, fraud models are not automatically high-risk and Article 10 data-governance duties would bite on credit models, not fraud models. Application dates for high-risk obligations may also have been moved by the 2025-2026 "digital omnibus" process. Verify both before relying on them.
- PRA, OCC and MAS expectations on lineage: not researched.
- DORA and GDPR lineage implications: not researched.
- Which lineage vendors banks actually use (named customers of Solidatus, Manta/IBM, Collibra, Informatica, Ab Initio): not researched.
- Card-scheme-specific requirements (PCI DSS data-flow diagrams and similar): not researched.

---

## 8. Emerging 2025-2026 themes

### Takeaway
The dominant 2026 theme is lineage and metadata as a "context layer" served to AI agents, typically through MCP servers; it is the stated rationale for most of the acquisitions and for analyst reframing. Data contracts are rising but, per Gartner as relayed, still early.

### Cited Findings
- Analyst reframing: BARC's 2026 report is headlined "From Data Catalog to Context Provider for AI Agents"; Forrester says governance "has entered the agentic era". **[analyst]** — [BARC](https://barc.com/news/from-data-catalog-to-context-provider-for-ai-agents/); [Forrester](https://forrester.com/blogs/the-forrester-wave-data-governance-solutions-q3-2025-shows-that-governance-entered-the-agentic-era)
- MCP servers exposing lineage: Solidatus 2026.3 (6 July 2026) adds MCP support to connect "governed data lineage to AI agents", plus an AI Lineage Assistant (March 2026) that runs on the customer's own LLM; Elementary Data ships an MCP server alongside column-level lineage. **[vendor-claimed]** — [Solidatus](https://www.solidatus.com/news/solidatus-launches-2026-3-product-update/); [IT Brief on the assistant](https://itbrief.com.au/story/solidatus-unveils-ai-assistant-to-automate-data-lineage); [Constellation Research on Boomi/Elementary](https://www.constellationr.com/insights/news/boomi-acquires-elementary-data-adds-data-observability-quality-governance-layer)
- Acquirers cite agent context as the reason for buying catalogs and lineage: Snowflake (Select Star, for Snowflake Intelligence and Cortex Code), ServiceNow (data.world, for AI agents on Workflow Data Fabric), Atlassian (Secoda, for Rovo), Fivetran + dbt Labs ("data infrastructure for trusted AI agents"). **[vendor-claimed]** — [Snowflake](https://snowflake.com/en/blog/snowflake-acquire-select-star/); [The New Stack](https://thenewstack.io/servicenow-acquires-data-world-to-expand-its-ai-data-strategy/); [TechTarget](https://www.techtarget.com/searchitoperations/news/366636012/Atlassians-Secoda-acquisition-adds-data-catalog-for-Rovo-AI); [Fivetran](https://www.fivetran.com/press/fivetran-dbt-labs-complete-merger-to-create-the-data-infrastructure-for-trusted-ai-agents)
- Lineage for agents themselves: Monte Carlo launched Agent Observability in March 2026 and lists Agent Lineage among 2026 features. **[vendor-claimed, via job-site profile]** — [Built In SF](https://www.builtinsf.com/company/monte-carlo/faq/stability-growth)
- DataHub repositioned as an "AI & data context platform" at its May 2025 rename. **[vendor-claimed]** — [Bessemer](https://www.bvp.com/news/bridging-the-ai-data-divide-with-datahub)
- Data contracts: Gartner predicts agents will turn governance policy into machine-verifiable data contracts at half of organizations by 2030; a 2026 Gartner abstract defines data contracts as machine-enforceable commitments certifying consistent delivery of data products. **[analyst]** — [Gartner press release, 11 Mar 2026](https://www.gartner.com/en/newsroom/press-releases/2026-03-11-gartner-announces-top-predictions-for-data-and-analytics-in-2026); [Gartner abstract](https://www.gartner.com/en/documents/7674661)
- Platform-native column lineage is being commoditised: Google Dataplex added column-level lineage for BigQuery at no extra cost (date not captured). **[vendor-claimed]** — [Google Cloud blog](https://cloud.google.com/blog/products/data-analytics/dataplex-supports-column-level-lineage-for-bigquery-data)
- Open table formats and catalogs: the 2024 Tabular, Polaris and Unity Catalog moves set up an open-catalog contest between Databricks and Snowflake. — [SiliconANGLE, 22 Jun 2024](https://siliconangle.com/2024/06/22/decoding-chess-moves-snowflake-databricks/)

### Inferences
- If agents become the main consumer of lineage, selection criteria shift from graph visualisation to API and MCP quality, freshness and machine-readable confidence. None of the analyst summaries retrieved score those explicitly.
- Free platform-native column lineage (BigQuery, and by extension Unity Catalog and Horizon) erodes the price a standalone vendor can charge for in-warehouse lineage; the defensible value moves to cross-system stitching and hard sources (stored procedures, ETL tools, BI, mainframe).

### Gaps
- OpenLineage adoption by hyperscalers (AWS, Google Cloud, Azure, Snowflake, Databricks): not researched.
- Effect of Iceberg and open catalogs (Polaris, open Unity Catalog, Iceberg REST) on lineage capture: not researched.
- MCP servers from Collibra, Alation, Atlan, DataHub, dbt and others: not researched, so the MCP finding rests on two small vendors.
- Shift-left evidence (Gable, data contracts in CI) and LLM-pipeline lineage standards: not researched.

---

## 9. Closing tables and open questions (requested by the brief)

### Takeaway
The tables consolidate the findings above. Rows marked "not verified" rely on my background knowledge or a single secondary source and must be sourced before publication.

### Cited Findings

**(a) Consolidation timeline**

| Date | Deal or event | Relevance to lineage | Status of evidence | Source |
|---|---|---|---|---|
| 2019 (not verified) | Collibra acquires SQLdep | SQL lineage parser became Collibra Lineage | Deal confirmed; year not verified | [Collibra](https://collibra.com/pressroom/collibra-announces-acquisition-of-sqldep) |
| Oct 2023 (not verified) | IBM acquires Manta | Specialist lineage now inside watsonx.data intelligence | Not verified this session | [IBM product page](https://www.ibm.com/support/pages/ibm-manta-data-lineage) |
| 3-4 Jun 2024 | Snowflake announces Polaris; Databricks buys Tabular ($1-2bn reported); Unity Catalog later open-sourced | Open-catalog contest | Confirmed | [The Register](https://www.theregister.com/2024/06/05/databricks_buys_tabular_for_1b/) |
| 8 May 2024 | Atlan $105M Series C, $750M valuation | Independent catalog funding | Confirmed | [TechCrunch](https://techcrunch.com/2024/05/08/atlan-scores-105m-for-its-data-control-plane-as-llms-boost-importance-of-data) |
| Nov 2024 | Cloudera acquires Octopai | Cross-platform lineage specialist absorbed | Confirmed | [Cloudera](https://www.cloudera.com/blog/business/octopai-acquisition-enhances-metadata-management.html) |
| Jan 2025 (not verified) | dbt Labs acquires SDF | SQL comprehension engine behind dbt Fusion | Not verified this session | none |
| Mar 2025 (not verified) | Coalesce acquires CastorDoc | Catalog joins transformation tool | Deal confirmed; date not verified | [TechTarget](https://www.techtarget.com/data-technologies/news/366621023/Coalesce-acquires-data-catalog-upstart-to-aid-transformation) |
| 23 Apr 2025 | Datadog acquires Metaplane | Column-lineage observability joins APM vendor | Confirmed | [TechCrunch](https://techcrunch.com/2025/04/23/datadog-acquires-ai-powered-observability-startup-metaplane) |
| 7 May 2025 (closed Q3 2025) | ServiceNow acquires data.world | Catalog for agent context | Confirmed | [TechCrunch](https://techcrunch.com/2025/05/07/servicenow-acquires-data-world-two-months-after-acquiring-moveworks) |
| 2025 (date not verified) | Alation acquires Numbers Station | Agentic AI for catalog | Deal confirmed; date not verified | [TechTarget](https://www.techtarget.com/data-technologies/news/366624026/Alation-boosts-agentic-AI-with-Numbers-Station-acquisition) |
| 21 May 2025 | Acryl Data renamed DataHub; $35M Series B (Bessemer) | Open-source lineage/catalog vendor funded | Confirmed | [SiliconANGLE](https://siliconangle.com/?p=697187) |
| 5 Jun and 24 Jul 2025 | Collibra acquires Raito and Deasy Labs | Access governance; unstructured data | Confirmed | [TechCrunch](https://techcrunch.com/2025/06/05/collibra-acquires-data-access-startup-raito/); [Collibra](https://www.collibra.com/company/newsroom/press-releases/collibra-acquires-deasy-labs) |
| 3 Sep 2025 | Fivetran acquires Tobiko Data (SQLMesh, SQLGlot) | Key open-source SQL lineage parser changes hands | Confirmed | [Business Wire](https://www.businesswire.com/news/home/20250903275106/en/Fivetran-Acquires-Tobiko-Data-to-Power-the-Next-Generation-of-Advanced-AI-Ready-Data-Transformation) |
| 13 Oct 2025 (closed 1 Jun 2026) | Fivetran and dbt Labs merge | Transformation lineage under one owner | Confirmed | [Fivetran](https://www.fivetran.com/press/fivetran-dbt-labs-complete-merger-to-create-the-data-infrastructure-for-trusted-ai-agents) |
| 18 Nov 2025 | Salesforce completes Informatica (~$8bn) | Largest governance and lineage suite now a Salesforce unit | Confirmed | [Salesforce](https://www.salesforce.com/news/press-releases/2025/11/18/salesforce-completes-acquisition-of-informatica/) |
| 24 Nov 2025 | Snowflake agrees to acquire Select Star | Column-lineage catalog folded into Horizon | Announced; close not verified | [Snowflake](https://snowflake.com/en/blog/snowflake-acquire-select-star/) |
| Dec 2025 (secondary date) | Atlassian acquires Secoda | Catalog folded into Rovo | Deal confirmed; date secondary | [TechTarget](https://www.techtarget.com/searchitoperations/news/366636012/Atlassians-Secoda-acquisition-adds-data-catalog-for-Rovo-AI) |
| 8 Jan 2026 | Snowflake agrees to acquire Observe | Telemetry observability (adjacent) | Confirmed | [Futurum](https://futurumgroup.com/?p=85406) |
| 10 Mar 2026 | Coalesce acquires SYNQ (becomes Coalesce Quality) | Lineage-aware observability joins transformation tool | Confirmed | [Coalesce](https://coalesce.io/company-news/coalesce-announces-acquisition-of-synq-and-launch-of-coalesce-quality/) |
| 17 Mar 2026 | Monte Carlo layoffs of about 30% (tracker-reported) | Viability signal for largest independent observability vendor | Third-party trackers only | [Blind](https://www.teamblind.com/layoffs/company/monte-carlo-data) |
| Oct 2026 | Boomi acquires Elementary Data | dbt-native observability with column lineage and MCP | Confirmed | [Constellation Research](https://www.constellationr.com/insights/news/boomi-acquires-elementary-data-adds-data-observability-quality-governance-layer) |
| Oct 2026 (unverified) | Collibra reported to acquire trail ML | AI compliance | Single secondary mention | see section 2 Gaps |

**(b) Pricing table** (annual, USD unless stated; all retrieved 26 Nov 2026 from search snippets)

| Vendor | Figure | Type | Sample / basis | Source |
|---|---|---|---|---|
| Collibra | Median $197,142 (range $174,740-$225,360) | Buyer-aggregator | Vendr, n about 6 | [Vendr](https://www.vendr.com/marketplace/collibra) |
| Collibra | $170,000 for 12 months | Marketplace list | AWS Marketplace | [AWS](https://aws.amazon.com/marketplace/pp/prodview-6gqg3yc2e2rsu) |
| Alation | From $60,000 for 12 months; connectors about $28,800-$30,000 each | Marketplace list | AWS Marketplace | [AWS](https://aws.amazon.com/marketplace/pp/prodview-ylge6fq43dtg6) |
| Alation | Range $76,044-$302,618 | Buyer-aggregator | Vendr, small n | [Vendr](https://www.vendr.com/marketplace/alation) |
| Atlan | Median $44,087-$49,764 (range about $24K-$132K) | Buyer-aggregator | Vendr, 26-43 purchases | [Vendr](https://vendr.com/marketplace/atlan); [CostBench](https://www.costbench.com/software/data-catalog/atlan/) |
| Atlan | From $100,000 for 12 months | Marketplace list | AWS Marketplace | [AWS](https://aws.amazon.com/marketplace/pp/prodview-4qh23e5eiqwow) |
| Informatica CDGC | £53,873.92 per year (GBP) | Public-sector list | UK G-Cloud 15, Jan 2026 | [UK Digital Marketplace](https://assets.applytosupply.digitalmarketplace.service.gov.uk/g-cloud-15/documents/703188/592589319296837-pricing-document-2026-01-29-1612.pdf) |
| Informatica CDGC | IPU consumption; no public $ per IPU | Rate card | Aug 2026 rate card via secondary | [Dawiso](https://www.dawiso.com/glossary/informatica-pricing) |
| IBM Manta | $87,821.99 per resource unit (Cloud Pak edition) | Reseller list | CDW | [CDW](https://cdw.com/product/manta-automated-data-lineage-for-ibm-cloud-pak-for-data-subscription-lice/7395092) |
| IBM Manta | 1 RU = 1 data source or 5,000 tables; list price not public | Vendor metric | IBM docs | [IBM](https://www.ibm.com/docs/en/DSXDOC/wsj/getting-started/wxdintell-plans.html) |
| Monte Carlo | Median $53,688 (range $12,970-$112,520); average $48,056 | Buyer-aggregator | Vendr, 54 and 26 deals | [Vendr](https://www.vendr.com/marketplace/monte-carlo); [Vendr guide](https://vendr.com/buyer-guides/monte-carlo) |
| Monte Carlo | $50,000 sample 12-month credit contract | Marketplace list | AWS Marketplace | [AWS](https://aws.amazon.com/marketplace/pp/prodview-hikicsfohm3gg) |
| Bigeye | Median $25,000 (range $15,000-$25,000) | Buyer-aggregator | Vendr, 10 purchases | [Vendr](https://vendr.com/marketplace/bigeye) |
| Bigeye | $75,000 Lineage Enterprise Starter Package | Marketplace list | AWS Marketplace (snippet) | [AWS](https://aws.amazon.com/marketplace/pp/prodview-fvnvwulb6kfbw) |
| Select Star | Median $36,000 | Buyer-aggregator | Vendr via CostBench, 13 purchases | [CostBench](https://costbench.com/software/data-catalog/select-star/) |
| DataHub Cloud | About $60,000-$75,000 (20 MAU) | Secondary report of marketplace list | Competitor and third-party pages | [Atlan](https://atlan.com/know/ai-agent/context-layer/datahub-pricing/) |
| Collate | Custom; not public | Vendor | Pricing page | [Collate](https://www.getcollate.io/pricing) |
| Datafold | Not found | n/a | Vendr has no data | [Vendr](https://vendr.com/buyer-guides/datafold) |
| Secoda | Not found (sales-led) | n/a | n/a | [TrustRadius](https://www.trustradius.com/products/secoda/pricing) |
| Solidatus | Not found (contact sales) | n/a | AWS listing | [AWS](https://aws.amazon.com/marketplace/pp/prodview-hgwtagukiojri) |
| Octopai | Not found (not researched) | n/a | n/a | none |

**(c) Quantified outcome claims with reliability rating**

| Claim | Objective | Provenance | Date | Reliability | Source |
|---|---|---|---|---|---|
| 61 incidents per month; 13 hours each to identify and resolve; 75% take 4+ hours to detect; about 9 hours to resolve | Incident detection/resolution (baseline of the problem) | Survey, vendor-funded (Monte Carlo / Wakefield), n about 300, self-reported | Apr-May 2022 | Low-medium; stale | [Business Wire](https://www.businesswire.com/news/home/20220809005223/en) |
| Data professionals spend 40% of time on data quality | Incident cost | Same survey | 2022 | Low; self-estimate | [BigDATAwire](https://www.hpcwire.com/bigdatawire/2022/08/12/monte-carlo-survey-finds-data-engineers-spend-40-of-their-workday-on-bad-data/) |
| 74% say business stakeholders find issues first all or most of the time (47% in 2022) | Incident detection | Survey, vendor-funded, n=200 | Mar 2023 | Low-medium; stale; large year-on-year swing suggests sampling noise | [APMdigest](https://apmdigest.com/data-downtime) |
| 67 incidents per month (59 in 2022); 31% of revenue impacted; downtime up 1.89x | Incident cost | Same survey | Mar 2023 | Low; 2022 baseline restated from 61 to 59 | [VentureBeat](https://venturebeat.com/data-infrastructure/data-downtime-almost-doubles-as-professionals-struggle-with-quality-issues-survey-finds/) |
| 358% ROI, $2.40M NPV, payback under 6 months | Incident detection/resolution | Vendor-commissioned Forrester TEI, 6 customers, composite model | Apr 2025 | Low as an outcome claim; useful as a cost sanity check | [Forrester TEI](https://tei.forrester.com/go/montecarlo/dataaiobservabilityplatform) |
| 364% ROI for Alation catalog | Baseline lineage/catalog | Vendor-commissioned Forrester TEI, 7 customers | Oct 2019 | Very low; seven years old | [Alation](https://www.alation.com/news-and-press/alation-data-catalog-delivers-364-return-on-investment-according-to-total-economic-impact-study/) |
| 53% have implemented data observability; 43% plan to within 18 months | Adoption | Gartner survey relayed by a vendor | 2025 | Medium for adoption; says nothing about outcomes | [Monte Carlo](https://www.montecarlodata.com/blog-what-2026-gartner-market-guide-for-data-observability-tools-means-for-your-data-and-ai-team-my-take/) |
| Collibra time to implement 6 months | Baseline lineage | Review-site aggregate (G2) | 2026 | Medium | [G2](https://www.g2.com/products/collibra) |
| Breaking changes caught pre-merge | Impact analysis | Not found | n/a | n/a | none |
| Incremental lineage freshness when sources change | Incremental lineage | Not found | n/a | n/a | none |
| Migration effort saved | Impact analysis | Not found | n/a | n/a | none |

**(d) Open questions**

- What do the paywalled Gartner cautions say about each leader's lineage depth, and does any 2026 report score column-level or attribute-level lineage explicitly? Needs licensed access or fetchable vendor reprints.
- Did the Snowflake-Select Star deal close, and is Select Star still sold for non-Snowflake estates? Same question for Secoda under Atlassian and Octopai under Cloudera.
- What do banks of comparable size actually pay for Collibra, Informatica, IBM Manta, Solidatus or Ab Initio lineage? No bank-scale price evidence was found; Vendr medians are mid-market.
- Is there any buyer-measured (not vendor-authored) before-and-after MTTD/MTTR evidence attributable to column-level lineage specifically? None found.
- What is the evidence for pre-merge impact analysis catching breaking changes (Datafold, dbt, SQLMesh, Recce, Foundational, Gable)? Not researched.
- What do Reddit r/dataengineering and Hacker News practitioners say? Search returned no thread content; needs direct site access.
- Build-versus-buy accounts with team size, timeline and cost: not researched.
- PRA, OCC, MAS expectations; EU AI Act Article 10 scope for fraud versus credit models and current application dates; DORA: not researched or not verified.
- OpenLineage adoption by hyperscalers and the effect of Iceberg / open catalogs on lineage capture: not researched.
- Are the unverified 2026 deals real (Collibra-trail ML, SAP-Reltio, ServiceNow-Veza, Snowflake-Natoma)?

### Inferences
- Across all four tables the same pattern holds: deal facts are well evidenced, prices are partly evidenced, and outcomes are barely evidenced. A report should say plainly that the market cannot currently prove, with independent data, that buying lineage shortens incidents or prevents breaking changes.

### Gaps
- See the open questions above. To close them, the session needs (1) a fresh web-search budget and (2) page fetching to work. The three hosts that failed to resolve were apmdigest.com, tei.forrester.com and dataopsleadership.substack.com; they need to be allowed in the session's network settings. No other host was tested after those failures, so it is unknown whether reddit.com, news.ycombinator.com, gartner.com, vendr.com, aws.amazon.com, bis.org, bankingsupervision.europa.eu or eur-lex.europa.eu are reachable; they would all be needed for full-page verification.
