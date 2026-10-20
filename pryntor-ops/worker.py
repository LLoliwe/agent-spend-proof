#!/usr/bin/env python3
"""Bounded, credential-free Pryntor public-source monitoring worker.
No LLM inference, paid API, secrets, external writes, or private company content.
"""
import datetime, json, os, urllib.request, urllib.error, uuid
from pathlib import Path

SOURCES = [
 ("github_status", "https://www.githubstatus.com/api/v2/status.json"),
 ("cloudflare_status", "https://www.cloudflarestatus.com/api/v2/status.json"),
 ("railway_status", "https://status.railway.com/api/v2/status.json"),
]
MAX_PROVIDER_BODY_BYTES = 65536


class StatusPayloadError(ValueError):
    """Provider response was received but cannot support a status claim."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


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
    return indicator, description


def record_response(item, response):
    """Record a provider response without treating malformed bodies as transport failures."""
    try:
        raw = read_bounded_body(response)
        if not 200 <= response.status < 300:
            raise StatusPayloadError("http_error")
        indicator, description = parse_status_payload(raw)
    except StatusPayloadError as exc:
        item.update(
            http_status=response.status,
            indicator="unverified",
            error=exc.code,
            evidence_type="invalid_provider_payload",
        )
    else:
        item.update(
            http_status=response.status,
            indicator=indicator,
            description=description,
            evidence_type="provider_status_api",
        )


def main():
    run_id = str(uuid.uuid4())
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    findings = []
    for name, url in SOURCES:
        item = {"source": name, "url": url, "checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat()}
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Pryntor-Operations-Watch/0.1"})
            try:
                with urllib.request.urlopen(req, timeout=8) as response:
                    record_response(item, response)
            except urllib.error.HTTPError as response:
                record_response(item, response)
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
    (output / "run.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"run_id":run_id,"sources":len(findings),"indicators":{i["source"]:i["indicator"] for i in findings},"output":str(output / "run.json")}))
if __name__ == "__main__": main()
