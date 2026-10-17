"""Pryntor offline database posture checker.

Consumes a sanitized, manually exported metadata snapshot. It does not open database
connections, load cloud credentials, read environment variables, or make changes.
Output contains rule codes and counts only, never source IPs or identifiers.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import sys
from pathlib import Path
from typing import Any

MAX_INPUT_BYTES = 65536
REQUIRED_COLLECTIONS = {"runtime_controls", "integration_registry", "jobs", "worker_heartbeats"}
QUEUE_INDEXES = {"jobs_ready_queue_v1", "jobs_expired_leases_v1"}
HEARTBEAT_INDEXES = {"worker_heartbeat_by_tenant_v1"}


def _fail(code: str, severity: str, detail: str) -> dict[str, str]:
    return {"code": code, "severity": severity, "detail": detail}


def _check_count(value: Any, name: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _index_names(collections: dict, name: str) -> set[str]:
    entry = collections.get(name, {})
    indexes = entry.get("indexes", [])
    if not isinstance(indexes, list) or any(not isinstance(i, str) for i in indexes):
        raise ValueError("collection indexes must be a list of names")
    return set(indexes)


def audit(snapshot: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(snapshot, dict) or snapshot.get("schema_version") != 1:
        raise ValueError("expected snapshot schema_version 1")
    collections = snapshot.get("collections")
    if not isinstance(collections, dict):
        raise ValueError("collections must be an object")
    findings: list[dict[str, str]] = []
    missing = REQUIRED_COLLECTIONS - set(collections)
    if missing:
        findings.append(_fail("MISSING_RUNTIME_COLLECTION", "high", f"{len(missing)} required collection(s) not in snapshot"))
    for name, val in collections.items():
        if not isinstance(val, dict):
            raise ValueError("collection entry must be an object")
        _check_count(val.get("count"), "collection count")
        _index_names(collections, name)
    if "jobs" in collections and not QUEUE_INDEXES.issubset(_index_names(collections, "jobs")):
        findings.append(_fail("QUEUE_INDEX_MISSING", "high", "Expected ready/lease indexes not both present"))
    if "worker_heartbeats" in collections and not HEARTBEAT_INDEXES.issubset(_index_names(collections, "worker_heartbeats")):
        findings.append(_fail("HEARTBEAT_INDEX_MISSING", "medium", "Expected heartbeat index not present"))

    net = snapshot.get("network_access", {})
    if not isinstance(net, dict):
        raise ValueError("network_access must be an object")
    networks = net.get("cidrs", [])
    if not isinstance(networks, list) or any(not isinstance(n, str) for n in networks):
        raise ValueError("network_access.cidrs must be an array of strings")
    broad = False
    for item in networks:
        try:
            parsed_network = ipaddress.ip_network(item, strict=False)
            broad = broad or parsed_network.prefixlen == 0
        except ValueError as exc:
            raise ValueError("invalid network CIDR entry") from exc
    if broad:
        findings.append(_fail("WIDE_NETWORK_ALLOWLIST", "critical", "At least one unrestricted CIDR; review scope"))
    if net.get("complete") is not True:
        findings.append(_fail("NETWORK_EVIDENCE_INCOMPLETE", "info", "Network listing completeness not verified"))

    control = snapshot.get("runtime_control")
    if not isinstance(control, dict):
        raise ValueError("runtime_control must be an object")
    for field in ("execution_enabled", "enqueue_enabled"):
        if type(control.get(field)) is not bool:
            raise ValueError(f"{field} must be boolean")
    ready = control["execution_enabled"] and control["enqueue_enabled"]
    hb_count = collections.get("worker_heartbeats", {}).get("count", 0)
    if ready and hb_count == 0:
        findings.append(_fail("RUNTIME_ENABLED_NO_HEARTBEATS", "critical", "Enabled runtime has no worker heartbeat evidence"))
    if control["execution_enabled"] != control["enqueue_enabled"]:
        findings.append(_fail("PARTIAL_EXECUTION_ENABLEMENT", "high", "Execution and enqueue flags differ"))
    if not ready:
        findings.append(_fail("RUNTIME_NOT_COMMISSIONED", "info", "Do not assert an active production worker"))

    backup = snapshot.get("production_backup")
    if backup is not None:
        if not isinstance(backup, dict):
            raise ValueError("production_backup must be an object")
        failure_count = _check_count(backup.get("recent_failures", 0), "recent_failures")
        restore = backup.get("restore_verified")
        if restore is not True and restore is not False and restore is not None:
            raise ValueError("restore_verified must be boolean or null")
        if failure_count > 0 and restore is not True:
            findings.append(_fail("BACKUP_RESTORE_UNVERIFIED", "critical", "Backup failures and no independently verified restore"))
        elif restore is not True:
            findings.append(_fail("RESTORE_PROOF_MISSING", "high", "No independently verified restore proof in snapshot"))
    else:
        findings.append(_fail("BACKUP_COVERAGE_UNKNOWN", "info", "Production backup was not assessed by this snapshot"))

    access = snapshot.get("access_metadata", {})
    if not isinstance(access, dict):
        raise ValueError("access_metadata must be an object")
    if access.get("users_enumeration_complete") is not True:
        findings.append(_fail("USER_ENUMERATION_UNVERIFIED", "info", "User enumeration is inconclusive"))
    rank = {"info": 0, "medium": 1, "high": 2, "critical": 3}
    findings.sort(key=lambda f: (-rank[f["severity"]], f["code"]))
    return {"schema_version": 1, "mode": "offline-read-only", "findings": findings,
            "summary": {"critical": sum(f["severity"] == "critical" for f in findings),
                        "high": sum(f["severity"] == "high" for f in findings),
                        "medium": sum(f["severity"] == "medium" for f in findings),
                        "info": sum(f["severity"] == "info" for f in findings)}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze sanitized database metadata; zero network/DB writes")
    parser.add_argument("file", type=Path, help="Sanitized JSON file")
    parser.add_argument("--fail-on-critical", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.file.stat().st_size > MAX_INPUT_BYTES:
            raise ValueError("metadata snapshot exceeds size limit")
        data = json.loads(args.file.read_text(encoding="utf-8"))
        result = audit(data)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        # Deliberately do not print the error contents, which might quote secret data.
        print(json.dumps({"error": "invalid_or_unreadable_snapshot", "type": type(exc).__name__}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 1 if args.fail_on_critical and result["summary"]["critical"] else 0


if __name__ == "__main__":
    sys.exit(main())
