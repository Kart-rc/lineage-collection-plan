# Metadata-only readiness helper

This candidate implements bounded readiness checks for WP-03 (supporting IN-10
and IA-1). It is a standalone Go executable with no external modules or shell
requirement. Parent orchestration mounts its static binary read-only at
`/lineage-healthcheck` in the target container.

```sh
/lineage-healthcheck http --url http://127.0.0.1:8014/readyz
/lineage-healthcheck http --url http://127.0.0.1:13133/
/lineage-healthcheck kafka --broker kafka:9092 --group accounting --topic orders
/lineage-healthcheck kafka --broker kafka:9092 --group fraud-detection --topic orders
```

Both modes accept `--timeout 5s`. The default is 5 seconds; valid overrides are
positive durations up to 30 seconds. Exit status is 0 when ready, 1 when unready,
and 2 for malformed CLI arguments. Only `ready` or a fixed failure category is
written to stderr. URLs, credentials, metadata values and response bodies are
never included in status output.

## Readiness conditions

HTTP performs one GET to the exact supplied URL. The endpoint must respond with
status **200**, without following redirects, and a complete body no larger than
16 KiB. Response headers are also bounded to 16 KiB. The body is discarded and
never interpreted or logged. Environmental proxies, connection reuse and
automatic response decompression are disabled. Normal TLS certificate checks
remain enabled for HTTPS; user-info credentials and URL fragments are rejected.

Kafka sends exactly one **DescribeGroups v0** request (API key 15) for the named
group. The broker must report zero error, the exact group, state `Stable`, protocol
type `consumer`, a selected nonempty group protocol and a member that has all of:

- Nonempty member and client IDs.
- A literal client-host IP equal to the probe's actual TCP connection local IP.
  Kafka's leading `/` and optional IPv6 brackets are normalized; hostnames are not
  resolved into an identity.
- A consumer assignment containing the requested topic with at least one
  nonnegative partition, decoded using consumer assignment versions 0–3.

Readiness does not require all group members to be local. A healthy member in
another container cannot make this container ready. Run the probe inside the
consumer's network namespace; running it from the host may correctly fail when
Docker NAT gives the broker a different observed client address.

The helper does not join a group, heartbeat, fetch records, consume messages,
produce, commit offsets or mutate Kafka metadata. Subscription metadata and
assignment user data are treated as opaque protocol metadata and skipped. No
Kafka message payload is requested, stored or logged.

## Protocol sources and bounds

The implementation was grounded in these official Apache Kafka 3.9.0 definitions,
read during implementation:

- [DescribeGroups request](https://github.com/apache/kafka/blob/3.9.0/clients/src/main/resources/common/message/DescribeGroupsRequest.json): API 15, version 0, group-name array, no flexible fields.
- [DescribeGroups response](https://github.com/apache/kafka/blob/3.9.0/clients/src/main/resources/common/message/DescribeGroupsResponse.json): version 0 has no throttle-time prefix; group error, identity, state, protocol and member fields.
- [Request header](https://github.com/apache/kafka/blob/3.9.0/clients/src/main/resources/common/message/RequestHeader.json) and [response header](https://github.com/apache/kafka/blob/3.9.0/clients/src/main/resources/common/message/ResponseHeader.json): non-flexible request header v1 and response header v0, including the correlation ID.
- [Consumer assignment schema](https://github.com/apache/kafka/blob/3.9.0/clients/src/main/resources/common/message/ConsumerProtocolAssignment.json): topic/partition arrays and nullable opaque user data, versions 0–3.
- [ConsumerProtocol serialization](https://github.com/apache/kafka/blob/3.9.0/clients/src/main/java/org/apache/kafka/clients/consumer/internals/ConsumerProtocol.java): `serializeAssignment` emits a version-prefixed buffer; `deserializeAssignment` first reads that int16 version.

All wire integers are big-endian. Kafka responses must have a complete signed
int32 length frame between 8 bytes and 1 MiB, the matching correlation ID, exactly
one requested group, and no trailing bytes. Individual strings are limited to
4096 bytes and valid UTF-8. Counts are nonnegative, must fit the remaining frame,
and are bounded to 1024 members, 1024 assignment topics and 65536 partitions per
topic. Duplicate topic/partition entries, null non-nullable fields and unknown
assignment versions fail closed. No allocation is sized directly from an
unvalidated wire count. The connection has a deadline for both reads and writes.
A constant correlation ID is safe here because each new TCP connection carries
one request and is closed after its one response.

## Build and checks

The task used the official Go 1.27.4 SDK. It needs a writable cache in this
sandbox; the system `/usr/bin/go` is unrelated and must not be used. There are no
module downloads. From this directory:

```sh
GOCACHE=/tmp/lineage-probe-go-cache GOTOOLCHAIN=local CGO_ENABLED=0 \
  /tmp/lineage-go-sdk-go1.27.4/go/bin/go test -count=1 ./...
GOCACHE=/tmp/lineage-probe-go-cache GOTOOLCHAIN=local CGO_ENABLED=0 \
  /tmp/lineage-go-sdk-go1.27.4/go/bin/go build -trimpath -ldflags='-s -w' \
  -o ../.state/bin/lineage-healthcheck .
```

The parent build creates `../.state/bin` and records the resulting artifact's
SHA-256. Tests use real local HTTP/TCP servers and independently encoded protocol
fixtures. They check exact GET paths, strict 200/no redirect, body bounds and
truncation, timeouts, request API/version/content, one-request-only behavior,
fragmented I/O, frame/correlation/count/string bounds, every truncation of valid
response/assignment fixtures, wrong groups/protocols/hosts/topics, partition
validity, known assignment versions, sanitized output and fuzz seeds.

This is deliberately a plaintext, single-broker twin probe. It has no SASL/TLS
Kafka support or coordinator discovery; a different broker or unsupported
protocol returns unready. It checks group membership and assignment metadata,
not whether the consumer processes business records successfully. Fresh load and
observed-edge checks are separate WP-03 acceptance evidence. Local protocol tests
cannot establish the three full cold-start passes or hosted consumer readiness.

## Local validation observed for this candidate

The Go suite passed on the first source build (10 test functions, their negative
subcases, and four fuzz seeds). Separate two-second bounded fuzz runs completed
62,732 DescribeGroups inputs and 39,950 assignment inputs without a failure.
`CGO_ENABLED=0` produced a statically linked ELF binary.

An additional real Kafka check used the existing local lineage broker and an
explicitly authorized temporary read-only, unprivileged container. A separate
fixture consumer joined a new empty synthetic topic/group; the helper ran in the
same container and returned ready for the assigned member. It returned unready
after that consumer closed. No records were produced or consumed; the exact
synthetic topic and group were deleted and the temporary container was removed.
The fixture consumer's join is test setup: the readiness helper itself still
sends only DescribeGroups. Actual accounting/fraud-detection container behavior
and full cold-start timing remain for the hosted twin run.
