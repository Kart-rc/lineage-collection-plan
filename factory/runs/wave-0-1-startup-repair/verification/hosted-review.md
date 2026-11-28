# Candidate 7 hosted evidence review

**FAIL for the hosted feasibility acceptance.** The original startup fault is resolved in this one measured trial, but sustained healthy collection and the precision measurement did not pass. The supplied metadata are internally consistent; no acceptance inflation was found.

## Identity and evidence

Run [46147235715](https://github.com/Kart-rc/lineage-collection-plan/actions/runs/46147235715), job 140985869153, executed merge commit `282433d4c933db13b57e9f9a557e65522607392e`. Root verified GitHub's mapping to PR head `aabfe7dadc404bead9a88161545c33c49fa6d62d`; publication, archive manifest, CI and hosted records agree on that head.

All five source hashes recorded by the pilot match the frozen independent review. The immutable candidate archive digest matches its manifest, and its five overlapping reviewed source/test/doc files match the frozen hashes. Worker image ID, probe SHA-256 and pinned demo identity agree between pilot and startup. The three hosted report SHA-256 values match `result.json`; embedded startup/smoke documents exactly match their standalone reports. No changing candidate-8 source was used.

## What the run establishes

| Check | Observed evidence | Conclusion |
| --- | --- | --- |
| One strict startup | 28 expected services, each present exactly once, running and healthy; initializer completed with exit 0; starter 132.522626 s and pilot observation 132.605541 s against 900 s | One readiness trial passed |
| Actual traffic window | 600.535933527 s; 5 users at baseline and all 21 observations; monotonic request count 11 → 593, delta 582 | Ten-minute actual traffic proof passed |
| Health during load | Exact 28-service inventory in every sample; 20/21 samples all healthy; final sample at 600.00009 s reports only lineage-collector running/unhealthy | Sustained all-service health failed |
| Forwarding | Accepted receipts 10 → 976; outbox sent 5 → 31; graph nodes 10 → 22, revisions 6 → 227, versions 6 → 1011 | Progress occurred; sustained healthy forwarding failed |
| Service-edge smoke | `blocked`, `invalid_otlp`, replay false, precision null | Precision was not scored |
| Shutdown | Current pilot reports acquired ownership and successful stop | Owned shutdown recorded |

The 132.6-second measurement is **one container startup after image/probe preparation**. Image/probe preparation and full build time are excluded; it does not establish all three required cold starts. Likewise, sampled healthy states are not proof of uninterrupted health between observations.

The forwarding failure is not a claim that no evidence reached the platform: receipts increased by 966, revisions by 221, and versions by 1005. The frozen pilot explicitly requires count progress **and** all load health samples healthy. The failed final health sample therefore makes `flow.holds` false. Diagnostic `sent: 0` describes the last collector iteration, not cumulative forwarding.

## Open failures and limits

1. **Collector capacity failure.** Last owned collector health is `error/input_limit`. Trace and log files total 17,731,133 bytes against the configured 16,777,216-byte bound, an excess of 953,917 bytes. The final health sample is unhealthy; the preceding 570.000076-second sample is healthy. These observations do not determine the exact failure onset. Disk and memory headroom remained above emergency limits (minimum 80,252,219,392 and 12,009,328,640 bytes respectively).
2. **Precision measurement blocked.** The scorer reports `invalid_otlp` during structural validation, before replay and precision scoring. This is not an observed precision-below-0.95 failure. File metadata show complete newline framing and no trailing bytes, which does not establish valid OTLP structure. Raw capture was not retained outside the disposable runner; the exact rejected record and its cause remain unknown. No causal link between this structural rejection and the collector's input bound is established by these records.

The separate CI run [46147235705](https://github.com/Kart-rc/lineage-collection-plan/actions/runs/46147235705) records three successful jobs and 481 reported unique cases. This review did not recompute deduplication from test artifacts and did not sum overlapping suite counts. Green CI does not override the full-reference pilot's failure.

WP-03 and Wave 0/1 remain incomplete. There is no 3/3 cold-start acceptance, measured precision floor, full IN-10/IA-1 p95 result, holdout result, G2 approval or G4 approval from this trial. Existing thresholds remain in force. This review performed only metadata/source-archive inspection and consistency checks, with no code fixes, test runs, infrastructure actions, remote mutations or raw-capture access.
