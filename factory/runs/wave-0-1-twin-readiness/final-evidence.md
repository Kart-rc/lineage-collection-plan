# Reference readiness candidate 6

The readiness tooling is locally verified and ready for one hosted feasibility
trial. Full WP-03 and Wave 0/1 acceptance remain incomplete.

## Change and evidence

- The starter enforces a maximum 900-second full-start deadline, checks the fixed
  inventory of 28 healthy long-running services, and separately verifies topic
  initialization. The pinned source renders that exact inventory without changes
  to the upstream checkout.
- The static standard-library Go helper checks HTTP readiness or read-only Kafka
  consumer-group assignment. HTTP/Kafka tests and 102,682 fuzz inputs passed.
  Real Kafka accepted the assigned local consumer and rejected it after closure;
  no records were produced or consumed. The final helper also passed the actual
  pinned flagd readiness endpoint.
- The pilot checks fresh project ownership, actual Locust users and request
  progress over at least 600 seconds, resource samples, accepted receipts, and
  positive persisted graph/outbox counts. The aggregate graph/archive query was
  verified read-only against the existing local worker.
- Offline smoke scoring uses the exact approved 0.95 precision floor and bounded
  parsing. Missing, malformed, truncated, changed, or oversized captures block.
  Raw captures and unrestricted diagnostics are excluded from published results.
- **109 focused Python checks passed**, with zero failures or skips; three live
  infrastructure checks were intentionally deselected. Go verification is
  recorded separately. The specification checker reports 0 errors; all eight
  G3-pinned oracle hashes match.
- Independent review closed all four candidate-5 findings: excessive startup
  timeout, a shrinking expected-service inventory, idle traffic accepted as load,
  and stale cleanup ownership. The final verdict is scoped `PASS_WITH_RISK`, with
  no open findings. See `verification/review.md` and `verification/verdict.json`.

## Measurement boundary

The new hosted job prepares the worker image and helper before measuring cold
container startup. It includes reference image pulls within the startup window.
It uploads only `pilot.json`, `startup.json`, and `smoke.json`. It never uploads
raw capture, collector logs, environment dumps, or Docker configuration dumps.

No full reference trial was performed locally: this host uses Docker vfs and
has less than 4 GiB free. Hosted results must be read from the exact workflow
run; local/mocked checks do not establish workload capacity or acceptance.
The first hosted run is one feasibility pilot, not the required three cold-start
trials. No acceptance claim is made until those measurements exist.

## Limits and remaining work

The carried-forward build ledger is **6 of 6**: four earlier candidates,
readiness candidate 5, and one consolidated review-repair candidate 6. Changing
hosts does not reset it. Further source repair requires a person to extend the
budget under constitution rule 9. Token usage is unavailable from the execution
interface and is recorded as unknown.

The pilot may expose full-workload capacity limits in the existing whole-capture
bridge. Its default 16 MiB input / 512 MiB parser limits have not been validated
against the complete workload. No bound or acceptance threshold was loosened
to obtain a passing result.

Remaining work includes three cold-start trials, ten-minute workload accuracy,
the traced end-to-end latency and fault scenarios, original-specific replay
inputs, independently managed holdout results, downstream integrations, and
human review/merge and release gates. Docker Neo4j Community remains the
authorized database target. No G2, G3 amendment, or G4 approval is inferred.
