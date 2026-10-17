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


## PR #8 security correction candidate (review-only, not merged)

This proposed change rejects missing `network_access`, missing CIDR lists, missing/invalid completeness booleans and duplicate JSON keys. The very broad CIDR detection now includes both `/0` and `/1` for IPv4 and IPv6. Whether to include `/2` and narrower ranges requires independent policy review. A listing with `complete: false` remains an explicitly incomplete finding, **not** security assurance.

**Two different exit-code contracts** must not be conflated:

- `mongo_snapshot_audit.py` retains its historic diagnostic CLI: exit `0` means parsing and audit completed, or with `--fail-on-critical`, no critical finding was detected; exit `1` means a critical finding when that flag was selected; exit `2` means invalid/unreadable input. Exit `0` is **not** approval for security, worker commissioning, or public release.
- `mongo_report_review_guard.py` is a **separate proposed** offline classifier of an already redacted audit report. Exit `2` invalid report; `3` blocked by any finding; `4` no findings but independent human review required. It has no approval exit code. The guard never connects to a database and cannot verify the truth or completeness of source metadata.

Reviewer decision checklist: assess the schema for authorized sanitized real-world metadata; agree on the CIDR risk threshold; examine duplicate-key handling, source-redaction, error sanitization and report envelope; explicitly decide whether a separate release command is necessary; verify that synthetic tests and exact-commit CI are not misrepresented as a production security review. Require an **independent GitHub reviewer not identical to the PR author**, and do not merge this proposal or PR #8 until review approval, exact-head CI and human release authorization are recorded. No MongoDB runtime flags, network permissions, databases or cloud services are modified by these files.
