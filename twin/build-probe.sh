#!/bin/sh
# Build the small static readiness client without downloading Go modules.
set -eu
LINEAGE_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
LINEAGE_GO_BIN=${LINEAGE_GO:-go}
LINEAGE_GO_VERSION=go1.27.4
case "$("$LINEAGE_GO_BIN" version)" in
  "go version $LINEAGE_GO_VERSION "*) ;;
  *) echo "Set LINEAGE_GO to the Go 1.27.4 compiler." >&2; exit 1 ;;
esac
mkdir -p "$LINEAGE_ROOT/twin/.state/bin"
cd "$LINEAGE_ROOT/twin/probe"
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 GOTOOLCHAIN=local GOWORK=off \
  GOCACHE="${LINEAGE_GO_CACHE:-$LINEAGE_ROOT/twin/.state/go-cache}" \
  GOPATH="$LINEAGE_ROOT/twin/.state/go-path" \
  "$LINEAGE_GO_BIN" build -mod=readonly -trimpath -buildvcs=false \
  -o "$LINEAGE_ROOT/twin/.state/bin/lineage-healthcheck.tmp" .
chmod 755 "$LINEAGE_ROOT/twin/.state/bin/lineage-healthcheck.tmp"
mv "$LINEAGE_ROOT/twin/.state/bin/lineage-healthcheck.tmp" \
   "$LINEAGE_ROOT/twin/.state/bin/lineage-healthcheck"
sha256sum "$LINEAGE_ROOT/twin/.state/bin/lineage-healthcheck"
