# WP-52: Terraform modules and service roles

Wave 5 · family platform · start level 2 · limits: 6 build attempts, 1 working day, cost recorded

**Serves:** XC-6  
**Depends on:** WP-00

## Scope

Neptune, MSK, Aurora, S3 and the services' roles in the platform account (D12, D19).

## Inputs

- docs/02-architecture-and-deployment.md

## Outputs

- planned:infra/

## Must hold

- No agent holds production credentials; KMS on every store; least privilege per service

## Done when

- Policy checks: 0 findings
- 1 named person's approval recorded for every plan diff applied
- Every visible scenario traced to the requirements above passes
- Holdout pass rate at or above the family rate in `factory/parameters.yaml`, where the family has holdout scenarios
- `python3 code/spec_pack.py --check` reports 0 errors

## Fixtures

- none

## Requirements

- **XC-6**: Where a model is used to read code, the system shall send only source code and schemas through the approved endpoint, and shall record the model, prompt version and output hash with the evidence. Scenarios: S-XC-06.
