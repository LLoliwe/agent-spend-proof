from proof.core import Ledger
from proof.workflows import creator_brief


def test_task_requires_simulated_paid_step(tmp_path):
    l = Ledger(str(tmp_path / "ledger.sqlite"))
    item = creator_brief(l, "sample-task", "examplecreator", "sample-idempotency-key")
    assert item["status"] == "synthetic_data_delivered"
    assert "SYNTHETIC" in item["result"]["data_provenance"]
    assert sum(ch["demo_share_pct"] for ch in item["result"]["channels"]) == 100
    assert item["paid"] is False
    assert item["intent"]["tx_hash"].startswith("SIM-")
    replay=creator_brief(l,"sample-task","examplecreator","sample-idempotency-key")
    assert replay["status"] == "replay_blocked"
    assert len(l.list())==1


def test_uncertain_task_has_no_output(tmp_path):
    l = Ledger(str(tmp_path / "ledger.sqlite"))
    r=creator_brief(l,"sample-task","examplecreator","sample-idempotency-key",outcome="unknown_settlement")
    assert r["status"]=="uncertain"
    assert r["result"] is None
