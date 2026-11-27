# WP-26: Access-history collector at column level: Postgres first, then Snowflake and Databricks

Wave 2 · family extractors · start level 3 (level 2 until wave 1 meets its holdout pass rate, D18) · limits: 6 build attempts, 1 working day, cost recorded

**Serves:** BL-3, XC-1  
**Depends on:** WP-11, WP-15

## Scope

Database client spans first, pg_stat_statements for clients without spans, statements parsed with SQLGlot down to columns; adapters for Snowflake ACCESS_HISTORY and Databricks lineage tables follow (D22, D27).

## Inputs

- code/observed_edges.py
- recorded query fixtures

## Outputs

- planned:collectors/access_history/

## Must hold

- Never attributes by login; never stores a literal or parameter value

## Done when

- Accounting writes 3 tables and 17 of 17 golden columns; product-catalog reads 8 columns of catalog.products
- 100% of the dbt job's reads attribute to analytics_dbt; 0 to astronomy_user
- A scan of the stored evidence finds 0 parameter values
- Every visible scenario traced to the requirements above passes
- Holdout pass rate at or above the family rate in `factory/parameters.yaml`, where the family has holdout scenarios
- `python3 code/spec_pack.py --check` reports 0 errors

## Fixtures

- `fixtures/otel-demo-3.1.0/capture-2026-11-27/observed-edges.json`

## Requirements

- **BL-3**: The system shall provide an extractor for each hop of the slice as listed under "Baseline: one extractor per hop". Scenarios: S-BL-01, S-BL-02, S-BL-06.
- **XC-1**: The system shall collect and store metadata only: names, schemas, expressions, counts and times. It shall not store payload values. Scenarios: S-XC-01, S-XC-08.
