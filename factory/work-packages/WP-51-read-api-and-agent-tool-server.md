# WP-51: Read API and agent tool server

Wave 5 · family platform · start level 3 (level 2 until wave 1 meets its holdout pass rate, D18) · limits: 6 build attempts, 1 working day, cost recorded

**Serves:** IA-9, XC-2, XC-5  
**Depends on:** WP-31, WP-42

## Scope

The four queries as a public API and as agent tools; /explain down to rawRef; personal-data roles.

## Inputs

- factory/specs/query-api/interfaces/openapi.yaml

## Outputs

- planned:services/api/

## Must hold

- Elements tagged personal are shown only to allowed roles

## Done when

- Contract tests against openapi.yaml: 100% pass, as API and as tools
- Access-control scenarios: 100% pass
- /explain traces 100% of sampled edges to a rawRef that exists in the archive
- Every visible scenario traced to the requirements above passes
- Holdout pass rate at or above the family rate in `factory/parameters.yaml`, where the family has holdout scenarios
- `python3 code/spec_pack.py --check` reports 0 errors

## Fixtures

- `factory/specs/query-api/interfaces/openapi.yaml`

## Requirements

- **IA-9**: The system shall expose the same impact query through an API that coding agents can call before a pull request exists. Scenarios: S-IA-10.
- **XC-2**: Every edge shall be traceable to its evidence records, and every evidence record to the raw input and the tool version that produced it. Scenarios: S-XC-02.
- **XC-5**: The system shall show elements tagged as personal data only to roles allowed to see them. Scenarios: S-XC-05.
