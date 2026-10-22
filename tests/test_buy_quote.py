import json
import pytest
from proof.buy_quote import inspect_quote, QuoteError
URL="https://gateway.usebuy.ai/cencori/v1/chat/completions"
BODY={"model":"maximo-atlas-1.3","max_tokens":256,
      "messages":[{"role":"user","content":"Say OK"}]}

def test_quote_does_not_pay():
    def fake(req):
        assert req.get_method()=="POST"
        assert "authorization" not in {k.lower() for k in req.headers}
        assert b"Say OK" in req.data
        return (402,{},json.dumps({"accepts":[{"amount":"10000","asset":"USDC"}]}).encode())
    result=inspect_quote(url=URL,body=BODY,transport=fake)
    assert result["no_payment_made"] and len(result["exact_body_sha256"])==64
    assert result["challenge"]["accepts"][0]["amount"]=="10000"

def test_blocks_bad_origins_and_nonquotes():
    bad=["http://gateway.usebuy.ai/a","https://gateway.usebuy.ai.evil.org/a",
         "https://name:pw@gateway.usebuy.ai/a","https://gateway.usebuy.ai:80/a"]
    for url in bad:
        with pytest.raises(QuoteError): inspect_quote(url=url,body=BODY)
    for status in (200,500):
        with pytest.raises(QuoteError,match="Expected unpaid 402"):
            inspect_quote(url=URL,body=BODY,transport=lambda req:(status,{},b""))
