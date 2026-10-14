"""Read-only Celo mainnet transfer evidence verifier. No wallet or payments."""
from __future__ import annotations
import json
from urllib.request import Request, urlopen

CELO_RPC = "https://forno.celo.org"
CELO_CHAIN_ID = 42220
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

class EvidenceError(ValueError):
    pass

def address(value: str) -> str:
    if not isinstance(value,str) or len(value)!=42 or not value.startswith("0x"):
        raise EvidenceError("Expected 20-byte EVM address")
    try: int(value[2:],16)
    except ValueError as e: raise EvidenceError("Invalid hexadecimal address") from e
    return value.lower()

def transaction_hash(value: str) -> str:
    if not isinstance(value,str) or len(value)!=66 or not value.startswith("0x"):
        raise EvidenceError("Expected 32-byte transaction hash")
    try: int(value[2:],16)
    except ValueError as e: raise EvidenceError("Invalid hexadecimal tx hash") from e
    return value.lower()

def hex_int(v):
    if not isinstance(v,str) or not v.startswith("0x"): raise EvidenceError("Invalid RPC integer")
    return int(v,16)

def rpc(method: str, params: list):
    if method not in {"eth_chainId","eth_getTransactionReceipt","eth_blockNumber"}:
        raise EvidenceError("Unapproved RPC method")
    req=Request(CELO_RPC,data=json.dumps({"jsonrpc":"2.0","id":1,"method":method,"params":params}).encode(),
        headers={"Content-Type":"application/json"},method="POST")
    with urlopen(req,timeout=7) as r: envelope=json.loads(r.read(200000))
    if envelope.get("error") or "result" not in envelope:
        raise EvidenceError("No usable RPC evidence")
    return envelope["result"]

def verify_transfer(*, tx_hash: str, token: str, payer: str, pay_to: str, amount_atomic: int,
                    rpc=rpc, min_confirmations: int=12) -> dict:
    """Validate an exact Celo ERC20 Transfer log, NOT service delivery or attribution."""
    tx_hash=transaction_hash(tx_hash)
    token,payer,pay_to=map(address,(token,payer,pay_to))
    if isinstance(amount_atomic,bool) or not isinstance(amount_atomic,int) or amount_atomic<1:
        raise EvidenceError("Positive integer atomic token amount required")
    if not isinstance(min_confirmations,int) or min_confirmations<12:
        raise EvidenceError("At least 12 confirmations required")
    if hex_int(rpc("eth_chainId",[]))!=CELO_CHAIN_ID: raise EvidenceError("Not Celo mainnet")
    receipt=rpc("eth_getTransactionReceipt",[tx_hash])
    if not receipt: raise EvidenceError("No mined receipt yet")
    if str(receipt.get("transactionHash","")).lower()!=tx_hash:
        raise EvidenceError("Receipt hash mismatch")
    if hex_int(receipt.get("status"))!=1: raise EvidenceError("Execution failed")
    block=hex_int(receipt.get("blockNumber"))
    confirmations=hex_int(rpc("eth_blockNumber",[]))-block+1
    if confirmations<min_confirmations: raise EvidenceError("Insufficient confirmations")
    sender="0x"+payer[2:].rjust(64,"0")
    receiver="0x"+pay_to[2:].rjust(64,"0")
    for event in receipt.get("logs",[]):
        topics=[str(t).lower() for t in event.get("topics",[])]
        if (str(event.get("address","")).lower()==token and len(topics)==3
                and topics==[TRANSFER_TOPIC,sender,receiver]
                and hex_int(event.get("data",""))==amount_atomic):
            return {"verified":True,"network":"celo-mainnet","chain_id":CELO_CHAIN_ID,
                    "tx_hash":tx_hash,"token":token,"payer":payer,"pay_to":pay_to,
                    "amount_atomic":amount_atomic,"block":block,"confirmations":confirmations,
                    "scope":"Token transfer only; delivery/attribution independently unverified"}
    raise EvidenceError("No matching transfer event")
