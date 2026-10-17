"""Review-only synthetic security regressions for PR #8. No live DB or secrets."""
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "posture_review", Path(__file__).resolve().parents[1] / "ops" / "mongo_snapshot_audit.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture():
    return {
        "schema_version": 1,
        "collections": {
            "runtime_controls": {"count": 1, "indexes": ["_id_"]},
            "integration_registry": {"count": 0, "indexes": ["_id_"]},
            "jobs": {"count": 0, "indexes": ["jobs_ready_queue_v1", "jobs_expired_leases_v1"]},
            "worker_heartbeats": {"count": 0, "indexes": ["worker_heartbeat_by_tenant_v1"]},
        },
        "runtime_control": {"execution_enabled": False, "enqueue_enabled": False},
        "network_access": {"cidrs": ["192.0.2.1/32"], "complete": True},
        "access_metadata": {"users_enumeration_complete": False},
    }


@pytest.mark.parametrize("cidr", ["0.0.0.0/0", "0.0.0.0/1", "128.0.0.0/1", "::/0", "::/1", "8000::/1"])
def test_detect_extremely_broad_networks(cidr):
    case = fixture()
    case["network_access"]["cidrs"] = [cidr]
    assert "WIDE_NETWORK_ALLOWLIST" in [f["code"] for f in module.audit(case)["findings"]]


@pytest.mark.parametrize("missing", ["network_access", "cidrs", "complete"])
def test_missing_network_evidence_rejected(missing):
    case = fixture()
    if missing == "network_access":
        del case[missing]
    else:
        del case["network_access"][missing]
    with pytest.raises(ValueError):
        module.audit(case)


@pytest.mark.parametrize("invalid", [None, 0, "yes", [], {}])
def test_malformed_complete_fails_closed(invalid):
    case = fixture()
    case["network_access"]["complete"] = invalid
    with pytest.raises(ValueError):
        module.audit(case)


def test_incomplete_network_is_marked_not_green():
    case = fixture()
    case["network_access"]["complete"] = False
    assert "NETWORK_EVIDENCE_INCOMPLETE" in [f["code"] for f in module.audit(case)["findings"]]


def test_ambiguous_duplicate_json_keys_exit_two(tmp_path, capsys):
    case = fixture()
    path = tmp_path / "ambiguous.json"
    payload = json.dumps(case).replace('"schema_version": 1,', '"schema_version": 1, "schema_version": 1,', 1)
    path.write_text(payload, encoding="utf-8")
    assert module.main([str(path), "--fail-on-critical"]) == 2
    assert "invalid_or_unreadable_snapshot" in capsys.readouterr().out


def test_broad_then_malformed_cidr_cannot_be_short_circuited():
    case = fixture()
    case["network_access"]["cidrs"] = ["0.0.0.0/0", "bad-cidr"]
    with pytest.raises(ValueError):
        module.audit(case)


def test_narrow_critical_flag_is_not_a_release_gate(tmp_path):
    case = fixture()
    path = tmp_path / "synthetic.json"
    path.write_text(json.dumps(case))
    assert module.main([str(path), "--fail-on-critical"]) == 0
    # Explicitly document: a zero exit means only that no critical findings were detected,
    # not that evidence is complete, runtime commissioned, or release approved.
    assert "RUNTIME_NOT_COMMISSIONED" in [f["code"] for f in module.audit(case)["findings"]]
