# Candidate 8: bounded collector capacity and OTLP validation

The user approved three additional repair attempts and one additional working
day; the cumulative cap is nine. This is candidate 8. Authorization and its
20:42 UTC November 28 deadline are preserved in
`../wave-0-1-startup-repair/approval.json`. The prior six attempts and candidate 7
are retained. No acceptance threshold or protected oracle changes are included.

## Measured trigger

[Candidate 7's hosted run](https://github.com/Kart-rc/lineage-collection-plan/actions/runs/46147235715)
started exactly 28 healthy services in 132.6 seconds, after image/probe
preparation. Five active users generated 582 additional requests during 600.5
seconds of load. This is one container-start measurement, not three successful
cold starts or total build time.

The collector was healthy in 20 of 21 load samples, then unhealthy at the final
sample. Its safe diagnostic recorded `input_limit`: traces and logs totaled
17,731,133 bytes, exceeding its 16,777,216-byte default. Forwarding occurred
(receipts 10 to 976; graph revisions 6 to 227; archive outbox sent 5 to 31), but
sustained healthy forwarding failed. Last-health `sent: 0` describes one collector
iteration, not the whole run. The minimum measured available memory was about
11.2 GiB, so the runner has room for a larger bounded profile.

Offline scoring separately stopped at `invalid_otlp`. Precision is unknown,
not a measured precision failure. The exact rejected record was not exported or
retained beyond the disposable runner. All five reported source hashes match the
frozen reviewed candidate. See the preserved `../wave-0-1-startup-repair/hosted/`
and independent `../wave-0-1-startup-repair/verification/hosted-review.md`.

## Repair and limits

The full-reference starter receives an explicit profile: 64 MiB combined live
input, 1 MiB per line, 4,096 events, 8 MiB metadata, 1,536 MiB parser address space,
30-second parsing deadline, and a 2 GiB collector container. Generic collector
defaults remain unchanged. The 128 sends per cycle, 100,000 acknowledged digests,
five-second send timeout and five-second polling interval remain bounded.
The profile provides about 3.8 times the measured ten-minute input, without
claiming arbitrary-duration streaming or one-hour acceptance.

The unchanged parser processed representative synthetic OTLP at about 18.8 MB,
56.5 MB and 67.1 MB. Near the 64 MiB bound it took about 8.9 seconds and used about
597 MB peak resident memory. The parser still rejects oversized input and retains
line/event/metadata guards. These are capacity experiments, not private holdout
cases or historical capture replay. Detailed measurements and their reproducible
script are in `checks/`.

Pinned OpenTelemetry file-exporter serialization legitimately omits empty
repeated fields at every level. The scorer now accepts those omitted fields as
empty arrays, while present containers must retain their correct types. Valid
empty exports cannot satisfy a nonempty precision requirement. Canonical span
identity checks and safe structural diagnostics are backed by the pinned pdata
serializer and OTLP specification. This repairs a locally proven validator defect;
it does not assert the identity of candidate 7's unavailable offending record.

If structural validation still fails, the runner reports only a filename enum,
line number, fixed schema path and fixed category. Raw keys, values, SQL, records
and arbitrary paths are excluded. Exact precision comparison at 0.95, source
fingerprints and replay/size/time/memory protections remain in force.

## Acceptance boundary

Local regression checks, independent source review and fresh hosted measurements
are distinct evidence. This packet does not by itself accept WP-03 or Wave 0/1.
Three cold starts, reference smoke precision, required end-to-end timings,
independent holdout results, original-specific replay and human release gates
remain applicable. Docker Neo4j Community remains the authorized graph target.
