# Requirements: core

Rendered from `factory/specs/requirements.yaml`. EARS phrasing; IDs as in doc 06.

| Id | Requirement | Verified by | Work packages | Visible scenarios |
| --- | --- | --- | --- | --- |
| BL-5 | The system shall store an indirect dependency once, from the source element to the target dataset, and shall not fan it out to every target column. | Graph size check on the join-heavy fixture: fct_order_value in the thin dbt model (fixtures/otel-demo-3.1.0/dbt) | WP-12, WP-20 | S-BL-05 |
| BL-7 | When the graph is rebuilt from the evidence lake, the system shall produce the same graph hash as the live graph at the same as-of time. | Replay determinism test | WP-04, WP-13 | S-BL-07 |
| IN-2 | When a unit is re-extracted, the system shall replace that unit's prior static evidence as one atomic set, closing any element edge the new extraction no longer supports. If one extraction would close more than a set share of an extractor's edges, then the system shall hold the write and raise an alert. | Removal scenarios: delete a column, delete a model; a broken-extractor scenario | WP-12 | S-IN-02, S-IN-03, S-IN-12 |
| IN-4 | The system shall write every edge version with valid-from, valid-to and recorded-at times, and shall never overwrite an edge in place. | Bitemporal property tests | WP-13 | S-IN-05 |
| IN-5 | The system shall return the graph as of any valid time, and the graph as it was recorded at any transaction time. | As-of scenarios on change C4 (tables move schema), including late-arriving access history | WP-13 | S-IN-05, S-IN-06 |
| IN-8 | When runtime evidence for an edge has not been seen for 30 days, the system shall mark the edge dormant and keep it. | Clock-advance scenario | WP-12 | S-IN-09 |
| IN-9 | When the same evidence is delivered more than once, the system shall leave the graph unchanged. | Idempotency property test | WP-12 | S-IN-10 |
