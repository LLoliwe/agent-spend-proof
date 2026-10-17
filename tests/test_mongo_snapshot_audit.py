"""Synthetic-only tests for the read-only posture checker."""
import importlib.util
import json
from copy import deepcopy
from pathlib import Path

spec = importlib.util.spec_from_file_location("mongo_snapshot_audit", Path(__file__).resolve().parents[1] / "ops" / "mongo_snapshot_audit.py")
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)


def fixture():
    return {"schema_version": 1,
            "collections": {
                "runtime_controls": {"count": 1, "indexes": ["_id_"]},
                "integration_registry": {"count": 3, "indexes": ["_id_"]},
                "jobs": {"count": 0, "indexes": ["_id_", "jobs_ready_queue_v1", "jobs_expired_leases_v1"]},
                "worker_heartbeats": {"count": 0, "indexes": ["_id_", "worker_heartbeat_by_tenant_v1"]}},
            "runtime_control": {"execution_enabled": False, "enqueue_enabled": False},
            "network_access": {"cidrs": ["192.0.2.10/32"], "complete": True},
            "access_metadata": {"users_enumeration_complete": False}}


def codes(snapshot):
    return [f["code"] for f in audit_module.audit(snapshot)["findings"]]


def test_disabled_runtime_is_not_called_production_ready():
    assert "RUNTIME_NOT_COMMISSIONED" in codes(fixture())
    assert "RUNTIME_ENABLED_NO_HEARTBEATS" not in codes(fixture())


def test_no_sensitive_ip_in_output():
    f = fixture()
    assert "192.0.2.10" not in json.dumps(audit_module.audit(f))


def test_wide_v4_network():
    f = fixture(); f["network_access"]["cidrs"] = ["0.0.0.0/0"]
    assert "WIDE_NETWORK_ALLOWLIST" in codes(f)


def test_wide_v6_network():
    f = fixture(); f["network_access"]["cidrs"] = ["::/0"]
    assert "WIDE_NETWORK_ALLOWLIST" in codes(f)


def test_bad_cidr_fail_closed():
    f = fixture(); f["network_access"]["cidrs"] = ["not-an-address"]
    try: audit_module.audit(f)
    except ValueError: return
    assert False


def test_missing_queue_index():
    f = fixture(); f["collections"]["jobs"]["indexes"] = ["_id_"]
    assert "QUEUE_INDEX_MISSING" in codes(f)


def test_missing_heartbeat_index():
    f = fixture(); f["collections"]["worker_heartbeats"]["indexes"] = ["_id_"]
    assert "HEARTBEAT_INDEX_MISSING" in codes(f)


def test_missing_collection():
    f = fixture(); del f["collections"]["jobs"]
    assert "MISSING_RUNTIME_COLLECTION" in codes(f)


def test_enabled_runtime_without_heartbeat_critical():
    f = fixture(); f["runtime_control"] = {"execution_enabled": True, "enqueue_enabled": True}
    assert "RUNTIME_ENABLED_NO_HEARTBEATS" in codes(f)


def test_partially_enabled_is_high():
    f = fixture(); f["runtime_control"]["execution_enabled"] = True
    assert "PARTIAL_EXECUTION_ENABLEMENT" in codes(f)


def test_restore_failure_critical():
    f = fixture(); f["production_backup"] = {"recent_failures": 4, "restore_verified": False}
    assert "BACKUP_RESTORE_UNVERIFIED" in codes(f)


def test_unknown_backups_not_claimed_healthy():
    assert "BACKUP_COVERAGE_UNKNOWN" in codes(fixture())


def test_no_user_enumeration_does_not_claim_absent_users():
    assert "USER_ENUMERATION_UNVERIFIED" in codes(fixture())


def test_wrong_count_type_fails_closed():
    f = fixture(); f["collections"]["jobs"]["count"] = True
    try: audit_module.audit(f)
    except ValueError: return
    assert False


def test_input_snapshot_not_mutated():
    f = fixture(); before = deepcopy(f)
    audit_module.audit(f)
    assert f == before


def test_offline_cli_success_and_no_secrets(tmp_path, capsys):
    f = fixture(); f["pretend_secret"] = "super-secret-not-for-output"
    p = tmp_path / "snapshot.json"; p.write_text(json.dumps(f))
    assert audit_module.main([str(p)]) == 0
    assert "super-secret" not in capsys.readouterr().out


def test_cli_critical_flag(tmp_path):
    f = fixture(); f["production_backup"] = {"recent_failures": 1, "restore_verified": False}
    p = tmp_path / "snapshot.json"; p.write_text(json.dumps(f))
    assert audit_module.main([str(p), "--fail-on-critical"]) == 1


def test_oversized_input_rejected(tmp_path, capsys):
    p = tmp_path / "oversize.json"; p.write_text(" " * (audit_module.MAX_INPUT_BYTES + 1))
    assert audit_module.main([str(p)]) == 2
    assert "invalid_or_unreadable_snapshot" in capsys.readouterr().out


def test_invalid_cidr_after_unrestricted_network_fails_closed():
    f = fixture(); f["network_access"]["cidrs"] = ["0.0.0.0/0", "bad"]
    try: audit_module.audit(f)
    except ValueError: return
    assert False
