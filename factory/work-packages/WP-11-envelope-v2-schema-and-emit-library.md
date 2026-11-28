# WP-11: Envelope v2 schema and emit library

Wave 1 · family core_semantics · start level 2 · limits: 6 build attempts, 1 working day, cost recorded

**Serves:** BL-2, BL-4, XC-1, XC-2, XC-3  
**Depends on:** WP-10

## Scope

The emit library every collector imports; it validates against envelope-v2.schema.json, sets weights from parameters.yaml and sends asynchronously.

## Inputs

- factory/specs/evidence/interfaces/envelope-v2.schema.json
- factory/parameters.yaml

## Outputs

- planned:collectors/evidence/

## Must hold

- Collectors cannot set their own weight
- No payload values - the library rejects any field outside the schema (XC-1)
- Emission is asynchronous and droppable (XC-3)

## Done when

- 100% of the schema's examples validate and 100% of the invalid examples are rejected
- v1 events from doc 03 upgrade to v2 with no field lost (fixture round trip)
- With the evidence broker stopped, a producer's p99 latency rises by less than 1 ms and nothing raises
- Every visible scenario traced to the requirements above passes
- Holdout pass rate at or above the family rate in `factory/parameters.yaml`, where the family has holdout scenarios
- `python3 code/spec_pack.py --check` reports 0 errors

## Fixtures

- `factory/specs/evidence/interfaces/envelope-v2.schema.json`
- `factory/specs/evidence/examples/`

## Requirements

- **BL-2**: When an extractor reads an extraction unit, it shall emit one evidence record per element mapping, carrying the dependency class and subtype, a hash of the normalized expression, and the extractor name and version. Scenarios: S-BL-01, S-BL-02.
- **BL-4**: If an extractor cannot resolve an element mapping, then it shall emit a dataset-level edge marked opaque with a reason code, and shall not drop the unit. Scenarios: S-BL-04, S-BC-06.
- **XC-1**: The system shall collect and store metadata only: names, schemas, expressions, counts and times. It shall not store payload values. Scenarios: S-XC-01, S-XC-08.
- **XC-2**: Every edge shall be traceable to its evidence records, and every evidence record to the raw input and the tool version that produced it. Scenarios: S-XC-02.
- **XC-3**: The system shall never block or slow a producer. All emission shall be asynchronous and droppable. Scenarios: S-BL-08, S-XC-03.
