# Requirements: extractors

Rendered from `factory/specs/requirements.yaml`. EARS phrasing; IDs as in doc 06.

| Id | Requirement | Verified by | Work packages | Visible scenarios |
| --- | --- | --- | --- | --- |
| BL-3 | The system shall provide an extractor for each hop of the slice as listed under "Baseline: one extractor per hop". | Golden graph recall per hop, on the hops of the reference slice listed in doc 06 (Baseline: one extractor per hop) | WP-20, WP-22, WP-23, WP-24, WP-25, WP-26, WP-28 | S-BL-01, S-BL-02, S-BL-06 |
| BL-6 | The baseline shall reach field-edge precision of at least 90% and recall of at least 90% against the golden graph once runtime evidence is on. | `lineage-eval score` on the reference slice: golden-graph.json plus the dbt golden edges | WP-01, WP-04, WP-19 | S-BL-01, S-BL-06, S-BL-08 |
| XC-4 | The system shall accept and emit OpenLineage events, including the column lineage facet, without loss of dependency class and subtype. | Round-trip test | WP-27, WP-50 | S-XC-04 |
| XC-6 | Where a model is used to read code, the system shall send only source code and schemas through the approved endpoint, and shall record the model, prompt version and output hash with the evidence. | Egress allow-list test; evidence field check | WP-29, WP-52 | S-XC-06 |
