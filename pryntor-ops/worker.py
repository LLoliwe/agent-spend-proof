#!/usr/bin/env python3
"""Bounded, credential-free Pryntor public-source monitoring worker.
No LLM inference, paid API, secrets, external writes, or private company content.
"""
import datetime, json, os, urllib.request, urllib.error, uuid
from pathlib import Path
from urllib.parse import urlsplit

SOURCES = [
 ("github_status", "https://www.githubstatus.com/api/v2/status.json"),
 ("cloudflare_status", "https://www.cloudflarestatus.com/api/v2/status.json"),
 ("railway_status", "https://status.railway.com/api/v2/status.json"),
]
MAX_PROVIDER_BODY_BYTES = 65536
VALID_STATUS_INDICATORS = frozenset({"none", "minor", "major", "critical"})


class StatusPayloadError(ValueError):
    """Provider response was received but cannot support a status claim."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def canonical_https_origin(url):
    """Return a stable HTTPS origin tuple or fail closed."""
    try:
        parsed = urlsplit(url)
        port = parsed.port or 443
    except (AttributeError, TypeError, ValueError) as exc:
        raise StatusPayloadError("unexpected_origin") from exc
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise StatusPayloadError("unexpected_origin")
    return parsed.hostname.lower(), port


class SameOriginHTTPSRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Block unsafe redirects before urllib sends a follow-up request."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        try:
            expected = canonical_https_origin(req.full_url)
            observed = canonical_https_origin(newurl)
        except StatusPayloadError as exc:
            raise urllib.error.HTTPError(
                newurl, code, "Blocked unsafe redirect", headers, fp
            ) from exc
        if observed != expected:
            raise urllib.error.HTTPError(
                newurl, code, "Blocked cross-origin redirect", headers, fp
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


STATUS_OPENER = urllib.request.build_opener(SameOriginHTTPSRedirectHandler())


def validate_response_origin(response, expected_url):
    """Reject redirects that leave the configured provider's HTTPS origin."""
    try:
        response_url = response.geturl()
    except (AttributeError, TypeError) as exc:
        raise StatusPayloadError("unexpected_origin") from exc
    observed = canonical_https_origin(response_url)
    if observed != canonical_https_origin(expected_url):
        raise StatusPayloadError("unexpected_origin")
    return f"https://{observed[0]}" + ("" if observed[1] == 443 else f":{observed[1]}")


def read_bounded_body(response):
    """Read at most the configured provider body limit and detect truncation."""
    raw = response.read(MAX_PROVIDER_BODY_BYTES + 1)
    if len(raw) > MAX_PROVIDER_BODY_BYTES:
        raise StatusPayloadError("oversized_body")
    return raw


def parse_status_payload(raw):
    """Return validated Statuspage-style fields or fail with a stable code."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise StatusPayloadError("invalid_json") from exc
    if not isinstance(data, dict) or not isinstance(data.get("status"), dict):
        raise StatusPayloadError("unexpected_schema")
    indicator = data["status"].get("indicator")
    description = data["status"].get("description")
    if not isinstance(indicator, str) or not indicator.strip():
        raise StatusPayloadError("unexpected_schema")
    if not isinstance(description, str) or not description.strip():
        raise StatusPayloadError("unexpected_schema")
    if indicator not in VALID_STATUS_INDICATORS:
        raise StatusPayloadError("unsupported_indicator")
    return indicator, description


def record_response(item, response, expected_url):
    """Record a provider response without trusting redirected evidence."""
    response_origin = "unverified"
    try:
        response_origin = validate_response_origin(response, expected_url)
        raw = read_bounded_body(response)
        if not 200 <= response.status < 300:
            raise StatusPayloadError("http_error")
        indicator, description = parse_status_payload(raw)
    except StatusPayloadError as exc:
        item.update(
            http_status=response.status,
            response_origin=response_origin,
            indicator="unverified",
            error=exc.code,
            evidence_type=(
                "invalid_provider_provenance"
                if exc.code == "unexpected_origin"
                else "invalid_provider_payload"
            ),
        )
    else:
        item.update(
            http_status=response.status,
            response_origin=response_origin,
            indicator=indicator,
            description=description,
            evidence_type="provider_status_api",
        )


def write_json_atomic(path, payload):
    """Replace a completed JSON artifact atomically or preserve the prior one."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    run_id = str(uuid.uuid4())
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    findings = []
    for name, url in SOURCES:
        item = {"source": name, "url": url, "checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat()}
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Pryntor-Operations-Watch/0.1"})
            try:
                with STATUS_OPENER.open(req, timeout=8) as response:
                    record_response(item, response, url)
            except urllib.error.HTTPError as response:
                record_response(item, response, url)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            item.update(indicator="unverified", error=type(exc).__name__, evidence_type="failed_request")
        findings.append(item)
    result = {
      "schema_version": 1, "run_id": run_id, "worker": "fury-9-public-status-probe",
      "role": "Systems Reliability & Security", "started_at": started,
      "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
      "actual_ai_inference": False, "external_paid_calls": 0, "spend_authorized": "R0",
      "findings": findings, "review_state": "awaiting_independent_review",
      "limitations": ["Status API observations are not proof of Pryntor internal infrastructure health", "No LLM reasoning or independent peer reviewer was invoked"]
    }
    output = Path(os.environ.get("GITHUB_WORKSPACE", ".")) / "pryntor-ops-output"
    output.mkdir(parents=True, exist_ok=True)
    write_json_atomic(output / "run.json", result)
    print(json.dumps({"run_id":run_id,"sources":len(findings),"indicators":{i["source"]:i["indicator"] for i in findings},"output":str(output / "run.json")}))
if __name__ == "__main__": main()



