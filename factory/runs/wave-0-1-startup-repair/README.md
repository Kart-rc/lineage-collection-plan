# Candidate 7: reference startup repair

The user approved up to three additional repair attempts and one additional
working day. The cumulative limit is nine; the six prior attempts and failed
hosted run remain recorded. This increment is candidate 7. See `approval.json`.

## Reproduction and root cause

The prior hosted trial reached 23 healthy services. Image-provider and
telemetry-docs remained unhealthy, leaving the frontend and load generator
unstarted. The trial produced no load or smoke acceptance result.

Both exact pinned Linux AMD64 images were pulled for isolated diagnostics only.
Their compressed images are about 38/40 MB; pulls were guarded by measured free
space with a 1.5 GiB reserve. No full local twin was started and no shared service
was stopped or changed. The diagnostic containers used no network, no published
ports, and the generated IPv4-only templates. Each exact diagnostic container
was removed afterward.

The first isolated test encountered the local Docker client's HTTP proxy rather
than the application. Its result is retained in
`checks/nginx-initial-network-isolation.json`; it does not establish the cause.
With HTTP proxy variables explicitly disabled, both services produced the same
controlled result in `checks/nginx-reproduction.json`:

| Health destination | Result in each pinned image |
| --- | --- |
| localhost | Connection refused, exit 1 |
| 127.0.0.1 | Success, exit 0 |
| IPv6 loopback | Connection refused, exit 1 |

Both applications remained running with no OOM. The image's localhost lookup
includes IPv6 loopback; the sandbox has removed its IPv6 listener. Changing only
the health destination to IPv4 fixes the reproduced check. The original wget
arguments are supported and retained.

## Repair and checks

The generated health checks for these two Nginx services now use `127.0.0.1`.
Their HTTP paths, commands, 5-second intervals/timeouts, and 20 retries remain
unchanged. The generated-config regression failed before this change and passes
afterward. The 53 scoped startup/fault/infrastructure-local tests passed; three
live infrastructure checks were deliberately deselected.

The actual pinned source still renders exactly 28 default services with health
checks, and the one-shot initializer remains separate. Upstream source is clean.
The full 900-second deadline and all load/precision/holdout/gate requirements
remain in force. A fresh hosted trial is required before claiming that this
repair resolves full-workload startup.

The pilot also records only allowlisted last-health metadata from its acquired
collector state, so a later integration failure can be diagnosed without raw
logs. This diagnostic does not alter any acceptance decision.

Independent review passed with risk and no open conformance findings: 116
deterministic checks passed, three live checks were excluded, and six independent
cleanup checks preserved current-invocation ownership. The spec checker reports
zero errors and all eight G3 pins match. Hosted measurements remain separate.
No protected
oracle or contract changes, merge, deployment or G2/G3/G4 approval are included.
