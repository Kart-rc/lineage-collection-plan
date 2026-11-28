# Readiness and gap recommendations

Implementation can continue. The Docker Neo4j Community target, local platform,
broker/graph transport, CI runner and reviewable draft changes are available.
Full Wave 0/1 acceptance remains incomplete. The last completed hosted trial
proved startup and active traffic, then exposed a collector capacity limit and
blocked scoring. Candidate 8 has local repairs and measurements; a fresh hosted
result is still required.

The prior stall was the repository's six-attempt repair limit. The user approved
three additional attempts and one additional working day. Candidate 8 is within
that extension; no new design decision is needed to publish and test it.

| Gap | Recommended action | Evidence needed |
| --- | --- | --- |
| Collector capacity | Validate the measured, bounded ten-minute profile. Before continuous operation, implement incremental parsing with durable checkpoints and source-change detection. | Healthy forwarding throughout actual load; measured input growth, memory and parse time. |
| Scoring and startup reliability | Accept canonical OTLP omitted empty lists while rejecting malformed data. Score the fresh capture and repeat startup on fresh runners against a frozen candidate. | Nonempty exact precision at least 0.95 after ten minutes; 3/3 startups within 900 seconds. |
| Independent holdout | Assign an independent test owner and connect a private job to the aggregate-only evaluation interface. A holdout is unseen test data managed outside the builder's implementation work. | Signed family pass rates and failure categories bound to the candidate, with private case custody preserved. |
| Original capture replay | Recover the original raw captures. If unavailable, label fresh runs separately and prepare a specific amendment for criteria requiring those originals. | Reproducible reports tied to original source hashes, or an approved criterion change. |
| End-to-end performance | Complete the traced impact/feedback integrations and measure producer overhead and the hour-long change/PR visibility scenarios. | Existing work-package scenarios and p95/p99 thresholds pass under real workload. |
| Formal acceptance | Review the exact contract amendment in PR #8 and implementation/evidence in PRs #9 and #10. | Required human gate records identify final commits and report/oracle hashes. |

The extension authorizes ongoing engineering repairs. It does not manufacture
holdout results, recover missing captures, or establish release acceptance.
The approved four design directions remain implemented; no request to approve
them again is needed.
