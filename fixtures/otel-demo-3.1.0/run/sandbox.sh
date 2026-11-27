#!/bin/sh
# For sandboxes without IPv6 or without permission to raise ulimit, like the build sandbox on 27 November 2026.
# Writes IPv4-only copies of three files from a demo checkout; sandbox.override.yaml mounts them.
#   sh sandbox.sh <demo checkout at 3.1.0> [output folder, default ./sandbox]
set -eu
demo=$1
out=${2:-./sandbox}
mkdir -p "$out"
grep -v 'listen \[::\]' "$demo/src/image-provider/nginx.conf.template" > "$out/image-provider.nginx.conf.template"
grep -v 'listen \[::\]' "$demo/src/telemetry-docs/nginx.conf.template" > "$out/telemetry-docs.nginx.conf.template"
sed 's/ip: {0, 0, 0, 0, 0, 0, 0, 0}/ip: {0, 0, 0, 0}/' "$demo/src/flagd-ui/config/runtime.exs" > "$out/flagd-ui.runtime.exs"
echo "wrote three IPv4-only files to $out"
