# WP-20: dbt and SQL extractor

Wave 2 · family extractors · start level 3 (level 2 until wave 1 meets its holdout pass rate, D18) · limits: 6 build attempts, 1 working day, cost recorded

**Serves:** BL-2, BL-3, BL-4, BL-5, IN-3  
**Depends on:** WP-10, WP-11, WP-18

## Scope

Read a dbt project at a commit and emit envelope v2 evidence for every model, with SQLGlot.

## Inputs

- fixtures/otel-demo-3.1.0/dbt/
- jaffle-shop (read-only corpus)

## Outputs

- planned:extractors/dbt_sql/

## Must hold

- SQLGlot only; no hand-written SQL parsing
- SELECT * expands against the input schema as of the commit
- An unresolved model emits an opaque edge with a reason code; it never raises

## Done when

- Thin dbt model: precision and recall >= 0.90 against golden-dbt.json (30 direct, 5 indirect)
- Metamorphic suite (alias rename, CTE reorder, reformat): 100% identical edges and expression hashes
- jaffle-shop: precision >= 0.90 on the sample a person labels in WP-02
- Every visible scenario traced to the requirements above passes
- Holdout pass rate at or above the family rate in `factory/parameters.yaml`, where the family has holdout scenarios
- `python3 code/spec_pack.py --check` reports 0 errors

## Fixtures

- `fixtures/otel-demo-3.1.0/dbt/golden-dbt.json`
- `fixtures/otel-demo-3.1.0/dbt/models/`

## Requirements

- **BL-2**: When an extractor reads an extraction unit, it shall emit one evidence record per element mapping, carrying the dependency class and subtype, a hash of the normalized expression, and the extractor name and version. Scenarios: S-BL-01, S-BL-02.
- **BL-3**: The system shall provide an extractor for each hop of the slice as listed under "Baseline: one extractor per hop". Scenarios: S-BL-01, S-BL-02, S-BL-06.
- **BL-4**: If an extractor cannot resolve an element mapping, then it shall emit a dataset-level edge marked opaque with a reason code, and shall not drop the unit. Scenarios: S-BL-04, S-BC-06.
- **BL-5**: The system shall store an indirect dependency once, from the source element to the target dataset, and shall not fan it out to every target column. Scenarios: S-BL-05.
- **IN-3**: When a schema version is registered or a tier 1 table's DDL changes, the system shall publish a schema-change event and re-extract every unit that reads the changed dataset. Scenarios: S-IN-04.
