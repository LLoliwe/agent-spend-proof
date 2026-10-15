#!/usr/bin/env python3
"""Bounded, credential-free Pryntor public-source monitoring worker.
No LLM inference, paid API, secrets, external writes, or private company content.
"""
import datetime, json, os, time, urllib.request, urllib.error, uuid
from pathlib import Path

SOURCES = [
 ("github_status", "https://www.githubstatus.com/api/v2/status.json"),
 ("cloudflare_status", "https://www.cloudflarestatus.com/api/v2/status.json"),
 ("railway_status", "https://status.railway.com/api/v2/status.json"),
]
def main():
    run_id = str(uuid.uuid4())
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    findings = []
    for name, url in SOURCES:
        item = {"source": name, "url": url, "checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat()}
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Pryntor-Operations-Watch/0.1"})
            with urllib.request.urlopen(req, timeout=8) as response:
                raw = response.read(65536)
                data = json.loads(raw)
                item.update(http_status=response.status, indicator=data.get("status", {}).get("indicator", "unknown"), description=data.get("status", {}).get("description", "unknown"), evidence_type="provider_status_api")
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
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
