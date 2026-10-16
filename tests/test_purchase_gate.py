import hashlib
import json
import pytest
from proof.purchase_gate import prepare_purchase, GateError

A="0x"+"1"*40
B="0x"+"2"*40
C="0x"+"3"*40
URL="https://gateway.usebuy.ai/cencori/v1/chat/completions"
BODY={"model":"maximo-atlas-1.3","max_tokens":256,"messages":[{"role":"user","content":"Reply OK"}]}


def quote(body=BODY, url=URL, network="eip155:42220", amt="10000", recipient=B, token=C):
    raw=json.dumps(body,sort_keys=True,separators=(",", ":")).encode()
    return {"status":"quote_only","no_payment_made":True,"url":url,"method":"POST",
            "exact_body_sha256":hashlib.sha256(raw).hexdigest(),
            "challenge":{"accepts":[{"scheme":"exact","network":network,"asset":token,
                                     "payTo":recipient,"maxAmountRequired":amt}]}}


def prepare(q=None, **kw):
    return prepare_purchase(quote=q or quote(), body=kw.pop("body",BODY), wallet=kw.pop("wallet",A),
                            token_decimals=kw.pop("token_decimals",6), human_max_units=kw.pop("human_max_units","0.01"), **kw)

def test_good_quote_makes_only_disabled_proposal():
    x=prepare().report()
    assert x["status"]=="PREPARED_NOT_APPROVED" and x["purchase_enabled"] is False
    assert x["no_payment_made"] and x["max_amount_atomic"]=="10000"

@pytest.mark.parametrize("bad_url",[
 "http://gateway.usebuy.ai/x", "https://evil.com/x", "https://gateway.usebuy.ai:444/x",
 "https://user@gateway.usebuy.ai/x", "https://gateway.usebuy.ai/x?more=1",
 "https://gateway.usebuy.ai/x#frag", "https://gateway.usebuy.ai\\@evil.com/x"])
def test_url_guard(bad_url):
    with pytest.raises(GateError): prepare(q=quote(url=bad_url))

def test_changed_body_fails():
    with pytest.raises(GateError, match="changed"): prepare(body={"model":"changed"})

def test_not_unpaid_fails():
    q=quote();q["no_payment_made"]=False
    with pytest.raises(GateError):prepare(q=q)

@pytest.mark.parametrize("network",["sepolia", "eip155:11155111", "ethereum", "celo-alfajores"])
def test_wrong_chain_fails(network):
    with pytest.raises(GateError, match="Celo mainnet"):prepare(q=quote(network=network))

@pytest.mark.parametrize("amt",["0", "-1", "1.1", 10000, "", "01"])
def test_bad_atomic_fails(amt):
    with pytest.raises(GateError):prepare(q=quote(amt=amt))

def test_amount_cap_enforced():
    with pytest.raises(GateError, match="exceeds"):prepare(human_max_units="0.009999")

def test_same_wallet_self_pay_fails():
    with pytest.raises(GateError,match="Self payment"):prepare(q=quote(recipient=A))

def test_invalid_wallet_fails():
    with pytest.raises(GateError):prepare(wallet="SIM-WALLET")

def test_wrong_token_address_fails():
    with pytest.raises(GateError):prepare(q=quote(token="0x123"))

def test_bad_decimals_fails():
    with pytest.raises(GateError):prepare(token_decimals=True)

def test_fingerprint_changes_when_quote_changes():
    assert prepare().approval_fingerprint != prepare(q=quote(amt="9999")).approval_fingerprint

def test_missing_offers_fails():
    q=quote();q["challenge"]["accepts"]=[]
    with pytest.raises(GateError):prepare(q=q)

def test_no_quote_payment_or_keys_in_report():
    p=prepare().report()
    assert "seed" not in str(p).lower() and "private" not in str(p).lower()
    assert "body" not in p

def test_forged_quote_method_rejected():
    q=quote();q["method"]="GET"
    with pytest.raises(GateError):prepare(q=q)

def test_no_automatic_selected_offer():
    with pytest.raises(GateError):prepare(offered_index=1)

def test_nonfinite_max_fails():
    for n in ["NaN","Infinity","-1"]:
        with pytest.raises(GateError):prepare(human_max_units=n)
