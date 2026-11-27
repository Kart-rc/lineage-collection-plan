# WP-17: Owner and tier overlay from the catalog file and service criticality

Wave 1 · family core_semantics · start level 2 · limits: 6 build attempts, 1 working day, cost recorded

**Serves:** IA-4, XC-5  
**Depends on:** WP-10

## Scope

OWNS edges at weight 0.50, tiers, and personal-data tags from the contracts' classification.

## Inputs

- fixtures/otel-demo-3.1.0/catalog.yaml
- fixtures/otel-demo-3.1.0/contracts/

## Outputs

- planned:collectors/catalog/

## Must hold

- Tiers follow service.criticality (critical 1, high 2, medium and low 3)

## Done when

- 100% of golden nodes have an owner and a tier
- 100% of columns classified personal in the contracts are tagged personal on their nodes
- Every visible scenario traced to the requirements above passes
- Holdout pass rate at or above the family rate in `factory/parameters.yaml`, where the family has holdout scenarios
- `python3 code/spec_pack.py --check` reports 0 errors

## Fixtures

- `fixtures/otel-demo-3.1.0/catalog.yaml`
- `fixtures/otel-demo-3.1.0/contracts/accounting.contract.yaml`

## Requirements

- **IA-4**: The report shall list downstream elements and assets by hop with owner, tier, edge state and confidence, following direct dependencies for value impact and reporting indirect dependencies separately as row-set impact. Scenarios: S-IA-01, S-IA-03.
- **XC-5**: The system shall show elements tagged as personal data only to roles allowed to see them. Scenarios: S-XC-05.
