# Independent readiness verification — candidate 6

**Verdict: PASS_WITH_RISK.** No open finding remains in the reviewed startup, probe, smoke scorer, pilot, or hosted-pilot workflow. This is a tooling review, not proof that the full reference twin starts or sustains a real workload. Full WP-03/Wave 0/1 acceptance remains **BLOCKED** by the unexecuted hosted/reference trials, remaining measurements and human gates.

The reviewer assessed WP-03, WP-19, the constitution and unchanged approved thresholds. Candidate 5 had four confirmed findings, recorded in `candidate5-findings.json`. They were batched into candidate 6, the final slot of the existing six-candidate budget. This review does not reset that budget or authorize candidate 7. The verifier made no implementation repairs, infrastructure changes, image pulls, full starts, external messages or gate approvals. No private holdout was accessed or reconstructed.

## Independent evidence

| Check | Result | Artifact |
| --- | --- | --- |
| Candidate 5 startup/smoke tests | 45 passed, 3.08 s | `candidate5-startup-smoke-tests.xml` |
| Candidate 5 pilot tests | 18 passed, 0.25 s | `candidate5-pilot-tests.xml` |
| Final startup/smoke tests | **64 passed, 2.69 s** | `candidate6-startup-smoke-tests.xml` |
| Final pilot tests | **34 passed, 0.40 s** | `candidate6-pilot-tests.xml` |
| Go readiness helper | 44 passing test/subtest/fuzz-seed records, zero failures; package 0.114 s | `candidate5-go-tests.jsonl` |
| Original startup negative probes | Over-900 and missing-service cases now fail safely | `startup-boundary-probe.py` |
| Independent load activity probes | Idle and flat counters block; active increasing counters pass after 600 measured mock seconds | `load-closure-probe.py` |
| Actual workflow cleanup block, with subprocesses mocked | Stale/missing/unowned tokens cause zero cleanup calls; matching current token permits only scoped Compose down | `workflow-cleanup-closure-probe.py` |
| Protected oracle check | All 8 G3 pins match | `oracle-check.json` |

Python tests used `/tmp/lineage-build-venv/bin/python`. Go tests used the verified installed Go 1.27.4 toolchain with a separate temporary cache and no third-party modules. Tests of the protocol helper used local ephemeral test servers, not shared infrastructure. Fake clocks/commands in pilot tests establish orchestration behavior, not 600 seconds of real load. The parent's actual Kafka helper check, pinned configuration render, aggregate flow-query validation and final 109-test run are separately recorded under `checks/`; they are not represented as verifier-executed full-twin acceptance.

## Candidate 5 findings and candidate 6 closure

**TR-1 — P1, startup deadline: CLOSED.** The original API accepted `timeout=1800`, then returned `passed` for all-healthy readiness at 901 seconds. The CLI also allowed the longer timeout. Final `twin/start.py:31` rejects nonfinite, nonpositive or over-900 full-start values, and `:247` validates before preparation/start commands. The independent reproducer now returns exit 1, status failed and no healthy claim. Platform-only diagnostic startup remains separately scoped. The pilot independently fixes the startup budget to 900 seconds and checks both observed and reported elapsed time; callers cannot add a longer startup option.

**TR-2 — P1, expected inventory: CLOSED.** Removing accounting from both the rendered configuration and observed rows originally produced `passed`, with `expectedServices: 27`, because the expected set came from the renderer. Final `twin/start.py:23` defines the pinned 28-service inventory; `:38` rejects a configuration whose service set differs from that inventory plus the one-shot topic initializer. Actual readiness still requires exact names, running state and healthy state; duplicates, unexpected names, missing probes and exited containers cannot pass. The same reproducer now fails with expectedServices fixed at 28. The pilot also validates its independent fixed inventory and the startup artifact's own service rows.

**TR-3 — P1, actual load activity: CLOSED.** Candidate 5 measured 600 seconds of container health without querying Locust activity. The pinned load-generator health check only tested its TCP web port, and host `LOCUST_AUTOSTART=false` could override startup. Candidate 6 forces autostart in `twin/start.py:148`. The pilot's bounded Locust query at `twin/pilot.py:55` / `:310` projects only availability, an allowed state, active-user count and the aggregate request counter. The baseline and every sample require running load with active users; counters must not reset and must increase over at least 600 measured seconds. Invalid, unavailable, idle, zero-user, flat or reset counters cannot produce a pass.

The independent closure probe keeps all 28 container health states healthy in every case. With idle Locust it reports blocked; with running users but a flat request counter it reports blocked; with active users and increasing counters it reports passed. Each case measures 600 mock seconds and issues 22 activity queries. The parser uses the aggregate row shape of the pinned demo's `locust==2.44.4`, a 1 MiB response limit, an 8-second child alarm and a 10-second outer command limit. It rejects ambiguous totals and invalid numeric types without exposing endpoint rows, request values, errors or URLs. This is sampled activity evidence, not a throughput or application-correctness claim.

**TR-4 — P1, stale cleanup ownership: CLOSED.** With an old matching acquired marker/report pair and a new report-write failure, the original workflow would accept the stale pair despite the new attempt being blocked, unowned and having executed zero Docker commands. Candidate 6 creates a fresh workflow token before measurement (`full-reference-pilot.yml:34`), passes it through `--invocation-id` (`:54`), and requires marker = current token = report before cleanup (`:86`). Pilot ownership is recorded only after fresh project/container/volume/state checks and persisted before starting the child.

The verifier executes the actual workflow cleanup Python block with subprocess calls mocked. Old matching files with a new token, missing token, and unowned report each produce zero cleanup calls. Only a matching current acquired pair produces `docker compose -p lineage-twin -f twin/.state/compose.yaml down`; there is no volume deletion or broad prune. Existing project, retained-volume and state refusals issue no stop or cleanup. A failed report write cannot turn old ownership into current authority.

## Reviewed limits and claims

The Go helper requires strict HTTP 200 without redirects, bounded headers/body and complete reads. Kafka uses one bounded DescribeGroups v0 request, exact group identity, stable consumer protocol and an assignment belonging to the probe connection's local container IP. It does not fetch, produce, join a consumer group or commit offsets. Malformed frames, counts, strings, truncation and invalid assignments fail closed. Output uses controlled categories; protocol values and payloads are not logged. This confirms metadata readiness, not consumer business processing.

The smoke scorer reads raw captures in place. It checks file inventory/fingerprints and complete JSONL, caps capture/line sizes, and runs parsing with memory, CPU and wall-time bounds. It compares precision as exact rational counts against 0.95, so rounding cannot turn a failure into success. Unknown endpoints remain counted but are redacted from reports; control edges stay separate. Sentinels in payloads and SQL do not enter artifacts or output. Smoke success applies to service-edge precision for that capture; it does not establish recall, full WP-19, original-capture acceptance or timings.

The workflow pins the reference commit and Go version, checks unchanged oracle hashes, and builds tools before the reported container-start measurement. Reference image pulls remain inside the 900-second start budget. Only the three allowlisted, sanitized JSON reports are uploaded and printed; raw OTLP and unrestricted subprocess diagnostics stay in ignored private state. Scoring occurs only after the acquired containers are stopped. Failed runs remain failed and are not automatically retried. No G2/G3/G4 approval, protected merge, holdout rate, full IN-10/IA-1 p95 or three successful cold starts is claimed.

A real hosted run has not been independently executed. The actual accounting/fraud-detection containers, complete 28-service startup under the deadline, sustained live load, capture size/resource fit and smoke accuracy still require that execution. A successful one-shot feasibility pilot is also insufficient for WP-03's three recorded cold-start trials and the remaining full-wave acceptance criteria. Docker Neo4j is the authorized target; Neptune is not a blocker.

Final reviewed sources, workflow, README and relevant test/configuration files are pinned in `source-hashes.json`. The machine-readable verdict retains the candidate counter, closed findings, evidence boundaries and remaining approvals.
