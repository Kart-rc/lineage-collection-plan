# Candidate 8 independent verification

**Verdict: CHANGES REQUIRED for a hosted trial whose success certifies the requested workload.** Two open findings concern the pilot's load-evidence gate. The collector-capacity and canonical-OTLP changes have no additional open finding from this review. No full WP-03 or wave acceptance is established.

## Reviewed identity and boundary

The reviewed candidate is the eight-file archive `artifacts/review-candidate-source.tar.gz`, SHA-256 `7c9f996483e9d95d1cb1d74aa0cb16b97411d999b469d27219c53fabd0cde420`, with published parent `aabfe7dadc404bead9a88161545c33c49fa6d62d`. All eight files matched the archive and external/embedded manifest at entry and final verification. Local Git HEAD is an older base and was not used as the candidate diff. Thirteen other source/requirement files matched the prior independent source manifest. Eleven original requirement/oracle/interface files were also checked against the local original Git content, and all eight approved G3 pins matched. The pinned upstream checkout is clean at `dedc0178918e260823323b8d95005a8cb924b007`.

The criteria are WP-03, `factory/parameters.yaml`, the constitution, the evidence envelope, and the assigned full-pilot requirement of at least 600 seconds of actual five-user load. This review read source and metadata evidence and ran local deterministic tests. It did not run Docker lifecycle commands, pull images, run the full workload, access or author holdouts, edit implementation/oracles, send remote messages, or mutate shared services. Prior hosted results are historical candidate-7 evidence only.

## Open findings

### V8-1 — P1: The pilot can pass with fewer than the required five users

`twin/pilot.py:488`, `:583`, and `:596` accept any positive `user_count`. This does not independently verify the five-user workload configured in `twin/start.py:200-201`. In a deterministic execution of the actual candidate, both one user and four users at the baseline and all 21 samples produced `status: passed`, `traffic.holds: true`, 600 measured mock seconds, and no failure category. All service, forwarding, and scoring observations were held valid, so the defect is isolated to the workload gate.

**Required correction:** bind the traffic observations to the declared five-user profile at the baseline and throughout the measured window. A configured value alone is insufficient. Preserve safe metadata-only failure reporting, the 600-second duration, and the existing exact precision/startup floors. Add regression cases for below-profile user counts and a mid-window drop; retain a five-user passing control.

Evidence: `traffic-boundary-probe.py` and `traffic-boundary-results.json`, cases `only_one_user_for_entire_window` and `four_users_for_entire_window`.

### V8-2 — P2: One final completion is enough to certify the whole load window

`twin/pilot.py:598-602` checks only that aggregate request counts do not decrease, while `:620-624` accepts any final increase over the baseline. With five reported users and a flat completed-request counter at every earlier observation, a single increment at the final sample produces `status: passed` and `traffic.holds: true` for the full 600 seconds. The observations therefore establish one completion somewhere in the window, not sustained request activity throughout it.

This is a **lack of sufficient window evidence**, not proof that the generator was inactive: long in-flight requests can also produce a flat completion counter. No new response-throughput or latency target is proposed.

**Required correction:** define and implement a conservative activity-evidence policy for the measured window. Use bounded, metadata-only evidence of request activity across the window; where completion counts are flat, either establish ongoing activity using a suitable additional observable or classify that interval as unproven and withhold the pilot success claim. Do not label a flat count as actual inactivity without supporting evidence, and do not invent a performance floor. Exercise prolonged-flat-then-final-increase and sustained-activity controls.

Evidence: `traffic-boundary-results.json`, case `five_users_only_one_request_at_final_sample`: 600 mock seconds, one request total growth, one increasing interval out of 21, yet a passing pilot.

## Passing checks and scope limits

- 327 tests passed across startup, smoke, pilot, and collector-bridge tests. An additional 11 static/fault tests passed; three live infrastructure tests were deliberately excluded. These are deterministic/local checks, not a live ten-minute trial.
- `code/spec_pack.py --check` returned zero errors. `scripts/check_oracle.py` matched all eight pins.
- The full-reference profile is finite: 64 MiB combined input, 1 MiB lines, 4,096 events, 8 MiB metadata, 1,536 MiB parser address space, a 30-second parse deadline, 2 GiB collector memory, 128 sends/cycle, and 100,000 acknowledged digests. Environment overrides cannot expand the profile. The collector remains on the lineage network with `lineage-kafka:9092`; capture mounts are read-only. Standalone defaults remain unchanged. The published synthetic capacity measurements are appropriately narrower than runtime acceptance; actual cgroup enforcement and workload headroom still need hosted measurement.
- An independent read of the pinned file-exporter/pdata sources confirmed pdata v1.65.0 and omission of empty repeated fields at export/resource/scope levels. The scorer accepts these canonical omissions, rejects wrong present container types and invalid span identities, and still blocks empty-only captures. It retains exact rational nonempty precision comparison at the approved 0.95 floor.
- Structural diagnostics are restricted to fixed filename/schema/category enums and a bounded physical line number. Worker and pilot projections reject or discard arbitrary fields; sentinel-based tests passed without payload leakage. Capture fingerprint/replay guards, parser limits, and source hashes remain active.
- The exact 28-service inventory, 900-second startup deadline, stop-before-scoring behavior, token-bound cleanup, and explicit false full-acceptance claims remain covered by passing tests. These results do not prove sustained live health/forwarding.

Candidate 8 consumes the second of the three additional authorized repair attempts; the cumulative cap remains nine. Any batched repair is candidate 9. Three qualifying cold starts, fresh measured load/health/forwarding and smoke precision, traced end-to-end timings, applicable holdout evidence, original-specific replay, and human G2/G4 remain outstanding. No prior failure or unavailable raw capture was reclassified as a pass.

Machine-readable evidence and final source fingerprints are in `verdict.json` and `source-hashes.json`. Temporary synthetic capture/SQLite test trees were removed; only small verifier scripts, metadata reports, and test XML remain.
