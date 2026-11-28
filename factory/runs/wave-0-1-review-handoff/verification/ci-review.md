# Independent CI handoff review

**Verdict: PASS_WITH_RISK.** Workflow-only review; no open findings. This does not approve protected merges, G2/G4 or full Wave 0/1 completion.

Compared with the prior 77-file review manifest, only `.github/workflows/verify.yml` changed; all 76 other pinned files still match. No implementation or test source changed in this continuation.

The two separate `python -m pytest` steps at workflow lines 23–26 keep runner tests in a fresh interpreter before the remaining local tests. Lines 72–75 apply the same process boundary in the Docker job. The runner test file is excluded only from the second local invocation and remains explicitly selected in the first invocation. No failure is suppressed with `continue-on-error`, shell success overrides, or softened assertions.

Independent collection of the exact workflow selections produced:

| Selection | Collected tests |
| --- | ---: |
| Local runner | 43 |
| Remaining local checks | 311 |
| Docker runner | 45 |
| Docker graph and transports | 19 |
| Unique union | **367 of 367** |

There are no omitted or unexpected tests and no runner/remainder overlap within either job. The static snapshot integration test is explicitly selected at line 75 and receives `LINEAGE_WORKER_IMAGE=lineage-platform:ci` at line 58, matching the built worker image at line 71. This selects its actual-container branch. Broker, Bolt and live-twin variables required by the other integration checks remain set.

Specification, oracle-integrity, parser self-test and demo checks remain at lines 19–22; source citations remain pinned and checked at lines 40–47. Both runner and remaining-suite JUnit paths are uploaded with `if: always()` in each job (lines 27–33 and 76–82). Infrastructure cleanup also remains unconditional at lines 83–85. `git diff --check` passes.

Evidence: `workflow-collection.json` contains exact collected node IDs and command arguments. The workflow SHA-256 is pinned in `verdict.json`. This review parsed the workflow and collected tests only; it did not run test bodies, build images, restart infrastructure, contact external services, or execute GitHub-hosted CI. Actual execution evidence is supplied separately by the parent. The existing full-wave evidence and human-gate limitations remain.
