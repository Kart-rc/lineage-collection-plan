# Candidate 9 independent verification

**Verdict: READY FOR A FRESH HOSTED FEASIBILITY TRIAL. Zero open conformance findings within this review scope.** Both candidate-8 traffic-evidence findings are closed by the frozen candidate-9 source and independent deterministic probes. This is a code-readiness verdict; no candidate-9 live measurement or full WP-03 acceptance is established.

The reviewed source is the eight-file archive `../artifacts/review-candidate-source.tar.gz`, SHA-256 `b949c4c263037eebe5b966a98eb1e5679c98a76c0ef5b96cfdfbde86e35a5f6b`, with published parent `aabfe7dadc404bead9a88161545c33c49fa6d62d`. All eight files match the archive and its external and embedded manifests at entry and final verification. Only `twin/pilot.py` and `tests/test_twin_pilot.py` differ from candidate 8. Local HEAD is an older base and is not the candidate identity or diff base.

The authoritative criteria read for this review were WP-03, `factory/parameters.yaml`, and `factory/constitution.md`, together with the assigned pilot requirement: exact 28-service healthy startup within 900 seconds, at least 600 seconds of observed configured five-user traffic, sustained health and growing forwarding evidence, nonempty exact service-edge precision at least 0.95, metadata-only reports, and invocation-bound cleanup ownership. This review did not modify implementation, oracle, parameters, or requirements.

## Closure of prior findings

**V8-1 — Closed.** `twin/pilot.py:490` requires the observed count to equal the declared five-user profile. The baseline and every sample also feed the sticky `all_active` result at lines 590 and 606. Independently executing the candidate with one, four, or six users for the window blocks the pilot. One user at baseline, a four-user sample midway through the window, and a four-user final sample also block; subsequent recovery does not erase the mismatch. The normal five-user control passes. These observations close the earlier demonstrated acceptance of one or four users.

**V8-2 — Closed.** `twin/pilot.py:608` records actual elapsed observation times and checks request-counter progress across the window. The reported policy is explicit: nominal 30-second samples and a 60-second activity-evidence window. Progress at the 60-second boundary is accepted, but a flat count at that boundary or any later progress observation leaves the interval unproven. The failure is sticky. Lines 640–653 also evaluate the final unobserved tail and require an overall increase.

The historical five-user / single-final-completion case now blocks with `load_progress_unproven`. Independent cases also block a large early burst followed by flat counts, completion only every 90 seconds, a 61-second delayed observation, and a 61-second tail after a resource probe. Five-user steady progress and one completion each 60 seconds pass. Flat completion counters are treated as insufficient activity evidence; the code does not infer that long in-flight requests are inactive and does not report a failed throughput or response-time objective. A conservative inability to prove this window may still block a live trial whose requests are in flight.

The original failed candidate-8 results remain unchanged in `../../wave-0-1-collector-capacity/verification/traffic-boundary-results.json`. This review preserves those failures and separately records candidate-9 outcomes in `traffic-boundary-results.json`; it does not rewrite historical outcomes.

## Evidence and unchanged safeguards

- **113 pilot tests passed**, zero failures, errors, or skips; see `pilot-tests.xml`. This reruns the changed orchestration plus its startup, health, forwarding, exact-precision, metadata projection, and cleanup-ownership regression coverage.
- **16 independent adversarial cases matched their expected outcomes**, including the four historical boundary cases. The independent probe uses the existing fake transport/clock fixture, selects its own inputs and expected decisions, denies real subprocess execution, and executes the actual candidate pilot. It also checks metadata sentinel exclusion, stop-before-scoring behavior, the complete mock measurement window, and false full-acceptance claims. Counter reset and unavailable-probe cases remain blocked after recovery.
- `code/spec_pack.py --check` returned **0 errors**; `scripts/check_oracle.py` matched **all 8 approved pins**. Spec-pack structural trace validation is not execution of the traced acceptance scenarios.
- The six unchanged frozen files, 13 supporting-source/requirement entries, six additional-source entries, and 11 original protected-file entries match candidate-8 independent fingerprints. The candidate-8 archive, review, source record, test XML, pinned upstream exporter inspection, and original boundary results also match their recorded hashes. This permits reuse of the unaffected collector-capacity and canonical-OTLP evidence rather than repeating broad suites. The earlier overall candidate-8 verdict remains CHANGES_REQUIRED; only its unaffected evidence is reused.
- Source review and the passing pilot suite show no regression to the fixed 28-service inventory, 900-second startup bound, 600-second minimum load window, monotonic forwarding check, exact nonempty precision calculation, bounded metadata projections, finite collector profile, or stop-before-scoring ordering. The unchanged workflow still binds cleanup to the fresh invocation token, ownership marker, and report; existing projects and stale ownership cannot authorize cleanup in the regression cases.

The activity policy is sampled evidence, not a claim of continuously observed service behavior or a load-performance SLO. Actual load, healthy services, forwarding, capacity headroom, cgroup enforcement, and service-edge precision still require the hosted candidate-9 run. No local mocked elapsed time is reported as measured runtime evidence.

## Scope and remaining acceptance

No Docker lifecycle commands, image pulls, full workload, shared-service mutation, production access, private holdout access or authorship, GitHub writes, comments, or merges occurred. All synthetic state, report fixtures, and SQLite files were under `/tmp` and were removed; only verifier scripts, metadata results, and test XML are retained here.

Candidate 9 is the final repair authorized by the extension: cumulative cap 9 and deadline 2026-11-28 20:42:29 UTC. This review does not authorize another repair or change a gate.

The next admissible evidence step is a fresh hosted feasibility trial of the exact reviewed source. Full WP-03 still requires three qualifying cold starts, actual ten-minute load and precision evidence, passing requirement-traced scenarios and timing evidence, validated change events, applicable independent holdout results, and human G2/G4 decisions. No wave completion, production readiness, or release approval is implied by this verdict.

Final fingerprints and the machine-readable verdict are in `source-hashes.json` and `verdict.json`.
