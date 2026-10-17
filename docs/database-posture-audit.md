# Pryntor Database Posture Audit | v0.1

This is **not a live database agent**. It is a deterministic, offline, read-only checker of deliberately sanitized metadata collected by an authorized human or connector. No connection strings, actual IP addresses, credentials, user identities, customer records, query text, environment variables or provider exports belong in source control.

Run `python ops/mongo_snapshot_audit.py /path/to/sanitized-snapshot.json` from the repository root. Optional `--fail-on-critical` exits 1 for a critical finding. Exit 2 signals malformed/oversized input. Existing `pytest -q` runs synthetic tests. Neither a passing test nor a warning-free snapshot verifies a production database or cures a finding.

Input schema v1: `schema_version: 1`; `collections` mapping of collection name to nonnegative `count` and `indexes` name list; `runtime_control` booleans `execution_enabled` and `enqueue_enabled`; `network_access` `cidrs` and `complete`; optional `access_metadata.users_enumeration_complete` and optional separately evaluated `production_backup.recent_failures` and `production_backup.restore_verified`. The report contains only rule codes, generic descriptions and severity counts, not the input metadata.

The queue index checks are Pryntor-specific contracts, not universal MongoDB advice. A low-volume collection may not need further indexes; inspect a real workload and query execution plan before suggesting one. A provider user-enumeration response cannot establish that access is secure unless coverage is independently verified.

Operational and release gates:
1. Reconcile Atlas users, IP restrictions and role scope through an authorized account administrator.
2. For every critical database, prove successful encrypted backup, separate owner-controlled durable storage and an independent restore into an isolated environment.
3. Before commissioning workers, prove isolated runtime, least-privilege identity, controlled secrets, signed synthetic job/heartbeat and append-only audit; never toggle production execution based only on package-install CI.
4. Require independent code review, CI and security review before merge. No direct production writes, index changes, permission changes, expensive services or cloud deployments are implemented by this utility.
5. Keep zero-new-spend-first and do not treat free-tier code or trial credits as unlimited commercial usage.

Live audit findings, identities, network metadata and production incident records belong only in the authorized company issue tracker, not this public repository.
