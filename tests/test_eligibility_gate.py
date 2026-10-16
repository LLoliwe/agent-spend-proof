import pytest
from proof.eligibility_gate import audit_evidence, EVIDENCE_FIELDS


def test_empty_blocked():
    o=audit_evidence({})
    assert o["ready_to_submit"] is False
    assert len(o["missing_or_invalid_fields"]) == len(EVIDENCE_FIELDS)


def test_email_only_does_not_count_as_submission():
    o=audit_evidence({"enrollment_email":"Loops House 2026-10-14 confirmed"})
    assert not o["ready_to_submit"] and not o["packet_fields_present"]


def test_simulated_tx_cannot_pass():
    o=audit_evidence({"celo_payment_tx":"SIM-123456789000000"})
    assert any(v["field"]=="celo_payment_tx" for v in o["missing_or_invalid_fields"])


def test_no_false_green_even_with_all_structured_fields():
    e={k:"https://real.org/document/123" for k in EVIDENCE_FIELDS}
    e.update(wallet_address="0x"+"1"*40,celo_payment_tx="0x"+"a"*64,
             third_party_provider="Unrelated service vendor", enrollment_email="Confirmed email evidence")
    p=audit_evidence(e)
    assert p["packet_fields_present"] is True
    assert p["ready_to_submit"] is False
    assert p["chain_transfer_verified"] is False


def test_fake_receipt_verifier_fails():
    p=audit_evidence({"celo_payment_tx":"0x"+"a"*64},verify_receipt=lambda _: {"verified": True})
    assert not p["chain_transfer_verified"]


def test_exact_true_verifier_still_manual():
    p=audit_evidence({"celo_payment_tx":"0x"+"a"*64},verify_receipt=lambda _: True)
    assert p["chain_transfer_verified"] and not p["ready_to_submit"]


def test_verifier_errors_fail_closed():
    def throw(_): raise RuntimeError("offline")
    assert not audit_evidence({"celo_payment_tx":"0x"+"a"*64},verify_receipt=throw)["chain_transfer_verified"]


def test_invalid_evidence_type():
    with pytest.raises(ValueError):audit_evidence([])
