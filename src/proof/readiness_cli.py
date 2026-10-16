"""Read-only submission-evidence packet checker. Does not contact Loops or Celo."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .eligibility_gate import audit_evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit completeness of Agent Spend Proof evidence (not eligibility certification)")
    parser.add_argument("packet", type=Path, help="Path to local JSON evidence packet; do not put private data in public source")
    args = parser.parse_args(argv)
    packet = json.loads(args.packet.read_text(encoding="utf-8"))
    result = audit_evidence(packet)
    print(json.dumps(result, indent=2))
    # An independent reviewer must still attest claims even when every field is present.
    return 2 if result["missing_or_invalid_fields"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
