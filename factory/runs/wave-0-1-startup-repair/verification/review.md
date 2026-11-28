# Candidate 7 independent verification

**PASS_WITH_RISK — suitable for the authorized fresh hosted feasibility trial.** No open conformance finding in the reviewed change. This is a source and deterministic-test verdict, not WP-03, Wave 0/1, G2, G4 or holdout acceptance.

The approval retains attempts 1–6 and permits candidate 7 within a cumulative cap of 9. The constitution and WP-03 remain the acceptance basis. Review identity is the frozen working-tree SHA-256 set in `source-hashes.json`; the local checkout HEAD differs from the published PR head. The prior reviewed archive hash matches its supplied identity, and its startup/pilot source hashes match the failed hosted record.

## Direct evidence

- Final focused suite: **116 passed, 3 live integration checks deselected, 2.92 seconds**. Command and exit status are recorded in `verdict.json`. The suite covers exact inventory, genuine health status, the shared 900-second deadline, failed/absent initializer, sanitized failures, 600-second scheduling, active traffic and monotonic request counters, exact precision, and ownership refusal.
- Pinned upstream `dedc0178918e260823323b8d95005a8cb924b007` is clean. An independent in-memory transformation of its actual YAML confirms that `twin/start.py:78` preserves both wget commands, HTTP paths, and timing/retry values while replacing only `localhost` with `127.0.0.1`. Its IPv4 listeners survive the existing sandbox transformation. Independent inventory is 23 demo plus 5 lineage long-running services.
- `twin/pilot.py:317` reads only the `health` row from the acquired collector database, in SQLite read-only/query-only mode with byte/query limits. It rejects invalid status/category/count/time fields and drops unknown fields. `twin/pilot.py:624` invokes it only after successful shutdown of an owned invocation. Its result does not change acceptance decisions. The tests cover payload sentinels, oversized records, unowned state and success/failure ordering.
- Six independent executions of the actual workflow cleanup script used a fully mocked subprocess. Only a current matching invocation token authorized the scoped Compose cleanup. Stale token pairs, either mismatched token, unowned state, and missing current token did not authorize cleanup.
- `code/spec_pack.py --check`: **0 errors**. `scripts/check_oracle.py`: **8/8 approved pins match**. Constitution, parameters, reference oracle, golden graph/dbt and checks match local Git HEAD. The archived smoke scorer and hosted workflow are unchanged. Among the 39 archived source files, only the two implementation files, their two tests, and twin README changed.

The root diagnostic files are supporting inputs, not independent full-workload proof. They record the same isolated symptom for both pinned images: localhost/IPv6 refusal and IPv4 success with HTTP proxies disabled. The earlier proxy-affected diagnostic is retained and not counted as causal proof. This verifier did not rerun Docker diagnostics.

## Remaining acceptance evidence

The prior hosted run at `3a80d63a15a3fcf3226e4d1bcb7f3e02914941e3` failed at startup after 195.449899 seconds: 23 healthy services, image-provider and telemetry-docs unhealthy, and frontend/proxy/load-generator unstarted. Topic setup exited zero. It produced no load window or smoke score.

Candidate 7 still needs a fresh hosted result proving the exact 28-service inventory, all running and healthy within 900 seconds, and the separately successful initializer; then at least 600 seconds of actual load and exact precision >= 0.95. Full WP-03 remains incomplete until 3/3 qualifying cold starts and its remaining visible, timing, holdout-where-applicable and human gate obligations are met. No thresholds or acceptance claims were relaxed.

No Docker start/pull/build/restart, full workload, remote mutation, implementation repair, raw capture or unrestricted process-log inspection was performed by this verifier. Durable writes are limited to this review, verdict and source-hash packet. Synthetic test temporary files are not workload evidence.

One initial verifier comparison assumed constitutional files were included in the narrow 39-file source archive and stopped on the missing member. The follow-up separately verified archive members, local Git baseline equality and approved G3 pins; this was not a candidate test failure.
