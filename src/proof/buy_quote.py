"""Unpaid x402 quote inspector. Never signs, pays, or follows redirects."""
from __future__ import annotations
import base64
import hashlib
import json
import urllib.error
import urllib.request
from urllib.parse import urlsplit

class QuoteError(ValueError):
    pass

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise QuoteError("Redirect blocked")

def send(req):
    opener=urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(req,timeout=7) as r:
            return r.status,dict(r.headers),r.read(120000)
    except urllib.error.HTTPError as e:
        return e.code,dict(e.headers),e.read(120000)

def inspect_quote(*,url:str,body:dict,method:str="POST",transport=send)->dict:
    p=urlsplit(url)
    if (p.scheme!="https" or p.hostname!="gateway.usebuy.ai" or p.username
            or p.password or p.port or p.fragment or not p.path.startswith("/")
            or p.path.startswith("//")):
        raise QuoteError("Only HTTPS gateway.usebuy.ai paths allowed")
    if method!="POST" or not isinstance(body,dict) or not body:
        raise QuoteError("Only exact POST with nonempty JSON body supported")
    raw=json.dumps(body,sort_keys=True,separators=(",",":")).encode()
    if len(raw)>32768: raise QuoteError("Request too large")
    req=urllib.request.Request(url,data=raw,method="POST",
        headers={"Content-Type":"application/json","Accept":"application/json"})
    status,headers,response=transport(req)
    if status!=402:
        raise QuoteError(f"Expected unpaid 402; got {status}. No payment attempted.")
    header=next((v for k,v in headers.items() if k.lower()=="payment-required"),None)
    try:
        if header:
            challenge=json.loads(base64.b64decode(header+"="*(-len(header)%4),validate=True))
        else:
            challenge=json.loads(response)
    except (ValueError,UnicodeError) as e:
        raise QuoteError("Malformed 402 challenge") from e
    return {"status":"quote_only","no_payment_made":True,"url":url,"method":method,
            "exact_body_sha256":hashlib.sha256(raw).hexdigest(),
            "challenge":challenge,
            "message":"Check exact token, chain, atomic amount and recipient before an independently approved purchase."}
