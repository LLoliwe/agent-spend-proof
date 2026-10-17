#!/usr/bin/env python3
"""Offline GPU procurement policy verifier; no network or credentials."""
import argparse
import pathlib
import sys

RULES = {
    "canonical": "docs/GPU_COST_GATE.md",
    "read_only": "read-only",
    "no_spend": "No self-hosting",
    "evidence": "PRY-223",
}

def check(text):
    return {name: needle.lower() in text.lower() for name, needle in RULES.items()}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+", type=pathlib.Path)
    args = parser.parse_args()
    failed = False
    for path in args.files:
        try:
            results = check(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError) as exc:
            print(f"FAIL {path}: {exc}")
            failed = True
            continue
        for name, ok in results.items():
            print(f"{'PASS' if ok else 'FAIL'} {path}: {name}")
            failed |= not ok
    return int(failed)

if __name__ == "__main__":
    sys.exit(main())
