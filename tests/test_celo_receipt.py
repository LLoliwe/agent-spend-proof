import pytest
from proof.celo_receipt import verify_transfer, EvidenceError, TRANSFER_TOPIC

TOKEN="0x"+"a"*40
PAYER="0x"+"b"*40
SELLER="0x"+"c"*40
TX="0x"+"d"*64

def fake_rpc(method,params):
    if method=="eth_chainId": return hex(42220)
    if method=="eth_blockNumber": return hex(125)
    return {"transactionHash":TX,"status":"0x1","blockNumber":hex(112),"logs":[
        {"address":TOKEN,"topics":[TRANSFER_TOPIC,"0x"+PAYER[2:].rjust(64,"0"),
                                "0x"+SELLER[2:].rjust(64,"0")],"data":hex(10000)}]}

def verify(**kwargs):
    args=dict(tx_hash=TX,token=TOKEN,payer=PAYER,pay_to=SELLER,
              amount_atomic=10000,rpc=fake_rpc)
    args.update(kwargs)
    return verify_transfer(**args)

def test_proves_exact_transfer():
    r=verify()
    assert r["verified"] and r["confirmations"]==14
    assert "unverified" in r["scope"]

def test_rejects_wrong_destination_amount_and_chain():
    for change in ({"pay_to":"0x"+"0"*40},{"amount_atomic":10001}):
        with pytest.raises(EvidenceError): verify(**change)
    with pytest.raises(EvidenceError):
        verify(rpc=lambda m,p: "0x1" if m=="eth_chainId" else fake_rpc(m,p))

def test_rejects_failed_and_insufficiently_confirmed():
    def unconfirmed(m,p):
        if m=="eth_blockNumber": return hex(112)
        return fake_rpc(m,p)
    with pytest.raises(EvidenceError,match="confirmations"):verify(rpc=unconfirmed)
    def failed(m,p):
        r=fake_rpc(m,p)
        if m=="eth_getTransactionReceipt":r["status"]="0x0"
        return r
    with pytest.raises(EvidenceError,match="failed"): verify(rpc=failed)
