import pytest
from proof.core import Ledger, PolicyError


def new(db, *, key="unique-key-1", amount=50, task="task-1", merchant="https://api.example.org", service="dataset"):
    return db.add(task,merchant,service,amount,"USD",key)


@pytest.fixture
def db(tmp_path):
    return Ledger(str(tmp_path / "ledger.db"))


def test_basic_simulation_no_money(db):
    intent, dup = new(db)
    assert not dup and intent["status"]=="approved" and intent["mode"]=="simulation"
    settled=db.simulate(intent["id"],"delivered")
    assert settled["status"]=="settled"
    assert settled["tx_hash"].startswith("SIM-")
    assert db.stats()["real_money_moved"] is False


def test_idempotency_and_conflict(db):
    a,_=new(db)
    b,dup=new(db)
    assert dup and a["id"]==b["id"]
    with pytest.raises(PolicyError, match="different request"):
        new(db,amount=60)


def test_no_double_execution(db):
    intent,_=new(db)
    db.simulate(intent["id"],"delivered")
    with pytest.raises(PolicyError):
        db.simulate(intent["id"],"delivered")


def test_vendor_rejected(db):
    a,_=new(db,merchant="http://api.example.org")
    b,_=new(db,key="unique-key-2",merchant="https://evil.example")
    c,_=new(db,key="unique-key-3",merchant="https://user:password@api.example.org")
    assert {a["status"],b["status"],c["status"]}=={"rejected"}


def test_request_and_task_limits(db):
    a,_=new(db,amount=251)
    assert a["status"]=="rejected"
    for n in range(4):
        it,_=new(db,key=f"other-key-{n+100}",amount=250)
        assert it["status"]=="approved"
    denied,_=new(db,key="other-key-999",amount=1)
    assert denied["status"]=="rejected" and "budget" in denied["reason"]


def test_fail_closed_on_uncertainty(db):
    intent,_=new(db)
    uncertain=db.simulate(intent["id"],"unknown_settlement")
    assert uncertain["status"]=="uncertain"
    with pytest.raises(PolicyError):
        db.simulate(intent["id"],"delivered")
    resolved=db.resolve(intent["id"],"not_settled","Receipt check: demo payment was not sent")
    assert resolved["status"]=="not_settled"
    with pytest.raises(PolicyError):
        db.simulate(intent["id"],"delivered")


def test_events_provide_audit_trail(db):
    a,_=new(db)
    db.simulate(a["id"],"missing_delivery")
    ev=db.events(a["id"])
    assert [e["event_type"] for e in ev]==["policy_decision","simulation"]
    assert db.stats()["simulated_settled_cents"]==50
