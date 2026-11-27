# Requirements: evidence

Rendered from `factory/specs/requirements.yaml`. EARS phrasing; IDs as in doc 06.

| Id | Requirement | Verified by | Work packages | Visible scenarios |
| --- | --- | --- | --- | --- |
| BL-1 | The system shall represent every field of every tier 1 asset in the slice as a node with the URN `<dataset URN>#<field path>`, using a dotted path for nested fields and `[]` for array items. | URN property tests; golden graph node check | WP-01, WP-10, WP-15, WP-21 | S-BL-01, S-BL-03, S-BL-09 |
| BL-2 | When an extractor reads an extraction unit, it shall emit one evidence record per element mapping, carrying the dependency class and subtype, a hash of the normalized expression, and the extractor name and version. | Envelope schema validation; fixture tests per extractor | WP-11, WP-20, WP-23, WP-24 | S-BL-01, S-BL-02 |
| BL-4 | If an extractor cannot resolve an element mapping, then it shall emit a dataset-level edge marked opaque with a reason code, and shall not drop the unit. | Opaque fixtures; gap count on the coverage report | WP-11, WP-20, WP-22, WP-23, WP-29 | S-BL-04 |
| XC-1 | The system shall collect and store metadata only: names, schemas, expressions, counts and times. It shall not store payload values. | Schema allow-list; scan of the evidence lake fixture | WP-11, WP-26 | S-XC-01, S-XC-08 |
| XC-2 | Every edge shall be traceable to its evidence records, and every evidence record to the raw input and the tool version that produced it. | Trace test from edge to `rawRef` | WP-11, WP-12, WP-51 | S-XC-02 |
| XC-3 | The system shall never block or slow a producer. All emission shall be asynchronous and droppable. | Fault-injection scenario | WP-11, WP-19, WP-53 | S-BL-08, S-XC-03 |
