# WP-21: Protobuf schema differ and registry watcher

Wave 2 · family extractors · start level 3 (level 2 until wave 1 meets its holdout pass rate, D18) · limits: 6 build attempts, 1 working day, cost recorded

**Serves:** BL-1, IN-3, IA-2  
**Depends on:** WP-10, WP-11

## Scope

Turn compiled descriptors into field nodes for every message on the slice; diff two versions into change kinds; publish schema-change events.

## Inputs

- pb/demo.proto at 3.1.0 and at the commits of C1 and C2

## Outputs

- planned:extractors/protobuf/

## Must hold

- Field identity is the field number within its message, not its name

## Done when

- 100% of golden api:// and kafka:// element nodes exist as fields
- C1 is reported as retyped (int32 to string, wire-incompatible); C2 as a package rename, wire-compatible
- A schema-change event is published within 1 minute of a descriptor change in the twin
- Every visible scenario traced to the requirements above passes
- Holdout pass rate at or above the family rate in `factory/parameters.yaml`, where the family has holdout scenarios
- `python3 code/spec_pack.py --check` reports 0 errors

## Fixtures

- `fixtures/otel-demo-3.1.0/change-replay.json`

## Requirements

- **BL-1**: The system shall represent every field of every tier 1 asset in the slice as a node with the URN `<dataset URN>#<field path>`, using a dotted path for nested fields and `[]` for array items. Scenarios: S-BL-01, S-BL-03, S-BL-09.
- **IN-3**: When a schema version is registered or a tier 1 table's DDL changes, the system shall publish a schema-change event and re-extract every unit that reads the changed dataset. Scenarios: S-IN-04.
- **IA-2**: The report shall list each changed element with its change kind: added, removed, renamed, retyped, nullability changed, logic changed, or row set changed. Scenarios: S-IA-01, S-IA-06.
