# Private grader boundary

No private store, job, credentials, or approved aggregate is configured. The local command is deliberately blocked until independent evidence exists. The public repository must never contain holdout cases or their texts.

The executable Python boundary is:

```python
from lineage.evaluation import run_private

result = run_private(
    {"candidate_commit": candidate_commit},
    runner=trusted_private_job_adapter,
    trusted=independently_installed_job_policy,
)
```

`trusted_private_job_adapter(request)` runs outside the build's trust domain. It receives only `candidate_commit` and the full G3 `oracle_sha256` mapping. The adapter must dispatch the already-built candidate to the independently controlled private runner, authenticate the job result, and return a JSON object conforming to [holdout-aggregate.schema.json](holdout-aggregate.schema.json). It must not return private inputs, case IDs, case texts, stack traces containing cases, or per-case results. Only aggregate counts, pass rates derived from them, and enumerated failure categories reach the builder.

A concrete local verification interface for an already retrieved aggregate is:

```sh
lineage-eval holdout --aggregate /absolute/path/authenticated-aggregate.json --trusted-policy /absolute/path/independent-policy.json --commit ACTUAL_COMMIT --output /tmp/holdout-verification.json
```

The trusted policy is installed by the independent job controller, not accepted from a candidate artifact. It contains `store_id`, `job_id`, `approved_by`, `independent_author`, `required_owner_signatures` (a nonempty array), and `aggregate_sha256`. The digest pins **canonical JSON bytes**: sorted keys, two-space indentation, a trailing newline, UTF-8. The adapter authenticates and pins the result before it reaches the builder; this tool validates those bindings. Merely writing one's own policy and matching aggregate is not independent evidence. Cryptographic transport/authentication and store ACLs belong to the independently operated adapter.

The aggregate contains:

- Provenance binding the store, job, run, candidate commit, eight oracle digests, independent author, platform approver, and the attestation that builders cannot read the cases.
- Counts of visible and private changes/incidents, broken down by every corpus family. Counts must add up, total at least 20 of each, hold at least seven of each privately, and keep at least one third of each family private.
- Per-evaluation-family totals, passed counts, and failure-category counts. Every failed case receives one primary category, so category counts sum to `total - passed`. Categories are the fixed enum `accuracy`, `coverage`, `schema`, `custody`, `timing`, `regression`, `hard_zero`, `unavailable`.
- Owner and platform-lead corpus signatures, and independent coverage attestations for near-simultaneous changes, silent failures, caller causes, targeting-rule flips, and no visible-case copies. These are verified through the trusted policy, not proof the builder could obtain by looking at private cases.

Unknown fields, arbitrary failure text, inconsistent counts, missing required family results, candidate/digest mismatches, and absent trust policy block verification. Malformed private payload errors are sanitized and do not echo input values. No configured runner returns `blocked`, not zero failures. IA-8 and IR-5 remain visible-only until a verified aggregate covers their families. These artifacts do not constitute a human G4 decision.
