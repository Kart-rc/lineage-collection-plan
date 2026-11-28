"""Check the existing G3 pins without rewriting the oracle or its approval."""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
record = ROOT / "factory/gates/G3-2026-11-28.md"
pins = re.findall(r"\| `([^`]+)` \| `([0-9a-f]{16,64})` \|", record.read_text())
if len(pins) != 8:
    raise SystemExit("G3 record does not contain the expected eight pins; review the oracle contract")
results = []
for name, expected in pins:
    actual = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    results.append({"path": name, "sha256": actual, "recorded_pin": expected, "matches": actual.startswith(expected)})
print(json.dumps({"gate_record": str(record.relative_to(ROOT)), "files": results}, indent=2))
raise SystemExit(0 if all(item["matches"] for item in results) else 1)
