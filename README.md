# Lineage collection: plan, architecture and starter kit

End-to-end lineage across microservices, streaming, analytics and ML features and models. The approach is top down. Gateway and mesh logs come first, then catalog and component overlay, then static code and runtime edges, proven on one vertical slice before widening. The graph is stored for impact analysis and used with data contracts and data quality checks for prevention, root-cause analysis and remediation.

Every example follows one illustrative card-payments slice:

`payments-svc → auth.events.v1 → txn-enrichment → auth.enrich.v1 → raw.card_auth → fct_card_auth → mcc_decline_7d → fraud-score-v12 → fraud-svc`

Service names, volumes, PR numbers and timings are examples, not measurements.

## What is here

| Path | What it is |
| --- | --- |
| [docs/01-implementation-plan.md](docs/01-implementation-plan.md) | The phased plan, phases 0 to 6 over about 18 weeks for the first slice. Covers the value and exit gate of each phase and the why behind each one. |
| [docs/02-architecture-and-deployment.md](docs/02-architecture-and-deployment.md) | Components, the four process flows and the AWS deployment. |
| [docs/03-collection-and-build-guide.md](docs/03-collection-and-build-guide.md) | How each collector sources its data and what it emits. Shows how five collectors merge into one graph (one envelope, one key), then a seven-step build with code skeletons. |
| [docs/04-research-appendix.md](docs/04-research-appendix.md) | Options, trade-offs and how leading tech companies approach lineage. |
| [docs/05-vendor-assessment-element-level-lineage.md](docs/05-vendor-assessment-element-level-lineage.md) | How lineage vendors get to element (column and field) level and where each stops, judged against four objectives: baseline lineage, incremental lineage when the source changes, impact analysis during code changes, and faster detection and resolution. Covers scanner suites, query-log catalogs and observability products, platform catalogs, CI tools and open source, with evidence grades. |
| [docs/06-element-lineage-factory-spec.md](docs/06-element-lineage-factory-spec.md) | Build spec for element-level lineage on the slice, delivered with an AI factory: requirements with IDs, the element model and envelope v2, the incremental engine, PR impact and RCA design, then the factory itself (oracle, stations, gates, 35 work packages, autonomy ladder, controls and metrics). |
| [docs/adr/ADR-002-own-the-lineage-graph-of-record.md](docs/adr/ADR-002-own-the-lineage-graph-of-record.md) | Draft ADR on build vs buy: own the thin lineage core, adopt the rest. |
| [site/lineage-starter-kit.html](site/lineage-starter-kit.html) | Interactive starter kit with two tabs. **The 30-day plan** has the prep list, a 22-working-day checklist, the first collector walkthrough, a simulator and the gate. **Assumptions, risks and readiness** covers inflows and outflows, the cost of acting vs not acting, 14 assumptions, a 5 whys, 10 rated risks and the day-1 checklist. |
| [site/lineage-components.html](site/lineage-components.html) | Interactive diagram of the 26 collection components in six layers. Each component shows its input and output, and five traces follow one event end to end. |
| [site/element-lineage-blueprint.html](site/element-lineage-blueprint.html) | Interactive explainer for docs 05 and 06 with five views. **Market** shows when each vendor family first sees a change and rates 28 products. **Fit to the slice** shows who sees fields on each of the eight hops. **What to build** traces the four flows on PR #482. **AI factory** shows the stations, gates and work packages. **Decide** holds the assumptions, alternatives and open decisions. |
| [research_notes/](research_notes/) | Working notes behind doc 05, one file per research thread, each finding tagged by how it was sourced. |
| [code/first_edges.py](code/first_edges.py) | Pure-Python script that builds CALLS edges from mesh access logs and scores them against a hand-checked golden graph. Run `python3 code/first_edges.py` to see the sample output. |

## Opening the pages

The three HTML files are self-contained apart from Google Fonts. Open any of them directly in a browser. To host them, turn on GitHub Pages for this repo with `/site` as the folder. Checklist ticks are saved in your browser only.

## Note on the markdown docs

The docs were exported from an editable document that also holds interactive visuals: a roadmap, a change simulator, per-phase diagrams, a component explorer and a merge visual. Markdown can't carry them. Each one appears as an `[embedded content: …]` line marking where it sits.

## Conventions used throughout

- **URNs:** `svc://prod/<name>`, `kafka://msk-prod/<topic>#field`, `warehouse://prod/<schema.table>#col`, `feast://fraud/<feature>`, `mlreg://fraud-score/12`
- **Edge types:** CALLS, PRODUCES and CONSUMES, READS and WRITES, DERIVES, FEEDS, SERVES, OWNS
- **Evidence weights:**
  - access_history and openlineage: 0.95
  - gateway_log and otel_span: 0.90
  - ci_static: 0.60
  - declared: 0.50
  - iam: 0.20
- **Confidence:** noisy-OR, `1 − ∏(1 − w)`.
- **Edge states:**
  - candidate: below 0.6
  - probable: 0.6 to 0.9
  - confirmed: 0.9 or above, with at least one runtime source
  - verified: owner confirmed
  - dormant: 30 days with no runtime evidence
  - retired
