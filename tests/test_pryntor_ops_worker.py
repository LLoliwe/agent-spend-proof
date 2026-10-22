import importlib.util
import http.client
import io
import json
import pathlib
import tempfile
import unittest
import urllib.error
import urllib.request
from unittest import mock


MODULE_PATH = pathlib.Path(__file__).parents[1] / "pryntor-ops" / "worker.py"
SPEC = importlib.util.spec_from_file_location("pryntor_ops_worker", MODULE_PATH)
worker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(worker)


STATUS_URL = "https://status.example/api"


class FakeResponse(io.BytesIO):
    status = 200

    def __init__(self, body, url=STATUS_URL):
        super().__init__(body)
        self.url = url

    def geturl(self):
        return self.url


class TruncatedResponse(FakeResponse):
    def read(self, _size=-1):
        raise http.client.IncompleteRead(b'{"status":', 100)


class StatusPayloadTests(unittest.TestCase):
    def test_accepts_complete_statuspage_payload(self):
        raw = json.dumps({"status": {"indicator": "none", "description": "All Systems Operational"}}).encode()
        self.assertEqual(worker.parse_status_payload(raw), ("none", "All Systems Operational"))

    def test_accepts_each_canonical_indicator(self):
        for indicator in sorted(worker.VALID_STATUS_INDICATORS):
            with self.subTest(indicator=indicator):
                raw = json.dumps({
                    "status": {
                        "indicator": indicator,
                        "description": "Provider supplied status",
                    }
                }).encode()
                self.assertEqual(
                    worker.parse_status_payload(raw),
                    (indicator, "Provider supplied status"),
                )

    def test_rejects_non_json_body(self):
        with self.assertRaisesRegex(worker.StatusPayloadError, "invalid_json"):
            worker.parse_status_payload(b"<html>not a status api</html>")

    def test_rejects_missing_status_object(self):
        with self.assertRaisesRegex(worker.StatusPayloadError, "unexpected_schema"):
            worker.parse_status_payload(b'{"message":"not found"}')

    def test_rejects_empty_indicator(self):
        raw = json.dumps({"status": {"indicator": "", "description": "Unknown"}}).encode()
        with self.assertRaisesRegex(worker.StatusPayloadError, "unexpected_schema"):
            worker.parse_status_payload(raw)

    def test_rejects_non_string_description(self):
        raw = json.dumps({"status": {"indicator": "none", "description": None}}).encode()
        with self.assertRaisesRegex(worker.StatusPayloadError, "unexpected_schema"):
            worker.parse_status_payload(raw)

    def test_rejects_unknown_indicator(self):
        raw = json.dumps({
            "status": {
                "indicator": "operational-ish",
                "description": "All Systems Operational",
            }
        }).encode()
        with self.assertRaisesRegex(worker.StatusPayloadError, "unsupported_indicator"):
            worker.parse_status_payload(raw)

    def test_rejects_duplicate_indicator_that_would_hide_a_critical_status(self):
        raw = (
            b'{"status":{"indicator":"critical","indicator":"none",'
            b'"description":"All Systems Operational"}}'
        )
        with self.assertRaisesRegex(worker.StatusPayloadError, "duplicate_field"):
            worker.parse_status_payload(raw)

    def test_records_duplicate_status_object_as_unverified(self):
        raw = (
            b'{"status":{"indicator":"critical","description":"Outage"},'
            b'"status":{"indicator":"none","description":"Operational"}}'
        )
        item = {}
        worker.record_response(item, FakeResponse(raw), STATUS_URL)
        self.assertEqual(item, {
            "http_status": 200,
            "response_origin": "https://status.example",
            "indicator": "unverified",
            "error": "duplicate_field",
            "evidence_type": "invalid_provider_payload",
        })

    def test_rejects_noncanonical_indicator_case_or_padding(self):
        for indicator in ("None", " none ", "MAJOR"):
            with self.subTest(indicator=indicator):
                raw = json.dumps({
                    "status": {
                        "indicator": indicator,
                        "description": "All Systems Operational",
                    }
                }).encode()
                with self.assertRaisesRegex(worker.StatusPayloadError, "unsupported_indicator"):
                    worker.parse_status_payload(raw)

    def test_records_unknown_indicator_as_unverified(self):
        raw = json.dumps({
            "status": {
                "indicator": "green",
                "description": "All Systems Operational",
            }
        }).encode()
        item = {}
        worker.record_response(item, FakeResponse(raw), STATUS_URL)
        self.assertEqual(item, {
            "http_status": 200,
            "response_origin": "https://status.example",
            "indicator": "unverified",
            "error": "unsupported_indicator",
            "evidence_type": "invalid_provider_payload",
        })

    def test_rejects_oversized_body_before_json_parse(self):
        response = FakeResponse(b"{" + b" " * worker.MAX_PROVIDER_BODY_BYTES)
        with self.assertRaisesRegex(worker.StatusPayloadError, "oversized_body"):
            worker.read_bounded_body(response)

    def test_records_http_status_for_invalid_error_response(self):
        response = urllib.error.HTTPError(
            STATUS_URL, 404, "Not Found", {}, io.BytesIO(b"<html>not json</html>")
        )
        item = {}
        worker.record_response(item, response, STATUS_URL)
        self.assertEqual(item, {
            "http_status": 404,
            "response_origin": "https://status.example",
            "indicator": "unverified",
            "error": "http_error",
            "evidence_type": "invalid_provider_payload",
        })

    def test_rejects_valid_looking_non_2xx_response(self):
        raw = json.dumps({"status": {"indicator": "none", "description": "All Systems Operational"}}).encode()
        response = urllib.error.HTTPError(
            STATUS_URL, 503, "Unavailable", {}, io.BytesIO(raw)
        )
        item = {}
        worker.record_response(item, response, STATUS_URL)
        self.assertEqual(item, {
            "http_status": 503,
            "response_origin": "https://status.example",
            "indicator": "unverified",
            "error": "http_error",
            "evidence_type": "invalid_provider_payload",
        })

    def test_records_oversized_provider_body(self):
        item = {}
        worker.record_response(item, FakeResponse(b"x" * (worker.MAX_PROVIDER_BODY_BYTES + 1)), STATUS_URL)
        self.assertEqual(item["http_status"], 200)
        self.assertEqual(item["indicator"], "unverified")
        self.assertEqual(item["error"], "oversized_body")
        self.assertEqual(item["evidence_type"], "invalid_provider_payload")

    def test_accepts_same_origin_redirect_path(self):
        raw = json.dumps({"status": {"indicator": "none", "description": "Operational"}}).encode()
        item = {}
        worker.record_response(item, FakeResponse(raw, "https://status.example/v2/status.json"), STATUS_URL)
        self.assertEqual(item["indicator"], "none")
        self.assertEqual(item["response_origin"], "https://status.example")

    def test_redirect_handler_allows_same_origin_https_path(self):
        request = urllib.request.Request(STATUS_URL)
        redirected = worker.SameOriginHTTPSRedirectHandler().redirect_request(
            request,
            io.BytesIO(),
            302,
            "Found",
            {},
            "https://status.example/v2/status.json",
        )
        self.assertEqual(redirected.full_url, "https://status.example/v2/status.json")

    def test_redirect_handler_blocks_unsafe_follow_up_requests(self):
        request = urllib.request.Request(STATUS_URL)
        for target in (
            "https://attacker.example/status.json",
            "http://status.example/status.json",
            "https://status.example:444/status.json",
            "https://user:pass@status.example/status.json",
        ):
            with self.subTest(target=target):
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    worker.SameOriginHTTPSRedirectHandler().redirect_request(
                        request, io.BytesIO(), 302, "Found", {}, target
                    )
                self.assertEqual(caught.exception.code, 302)

    def test_rejects_cross_origin_valid_looking_payload_without_reading_it(self):
        raw = json.dumps({"status": {"indicator": "none", "description": "Operational"}}).encode()
        response = FakeResponse(raw, "https://attacker.example/status.json")
        item = {}
        worker.record_response(item, response, STATUS_URL)
        self.assertEqual(item, {
            "http_status": 200,
            "response_origin": "unverified",
            "indicator": "unverified",
            "error": "unexpected_origin",
            "evidence_type": "invalid_provider_provenance",
        })
        self.assertEqual(response.tell(), 0)

    def test_rejects_https_downgrade(self):
        raw = json.dumps({"status": {"indicator": "none", "description": "Operational"}}).encode()
        item = {}
        worker.record_response(item, FakeResponse(raw, "http://status.example/api"), STATUS_URL)
        self.assertEqual(item["error"], "unexpected_origin")
        self.assertEqual(item["evidence_type"], "invalid_provider_provenance")

    def test_rejects_userinfo_and_nondefault_port(self):
        for url in (
            "https://status.example@attacker.example/api",
            "https://status.example:444/api",
        ):
            with self.subTest(url=url):
                item = {}
                worker.record_response(item, FakeResponse(b"{}", url), STATUS_URL)
                self.assertEqual(item["error"], "unexpected_origin")


    def test_truncated_response_does_not_abort_other_provider_evidence(self):
        healthy = json.dumps({
            "status": {
                "indicator": "none",
                "description": "Operational",
            }
        }).encode()
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(worker, "SOURCES", (
                ("truncated", "https://status.example/truncated"),
                ("healthy", "https://status.example/healthy"),
            )):
                with mock.patch.object(
                    worker.STATUS_OPENER,
                    "open",
                    side_effect=(
                        TruncatedResponse(b"", "https://status.example/truncated"),
                        FakeResponse(healthy, "https://status.example/healthy"),
                    ),
                ):
                    with mock.patch.dict("os.environ", {"GITHUB_WORKSPACE": directory}):
                        worker.main()

            result = json.loads(
                (pathlib.Path(directory) / "pryntor-ops-output" / "run.json")
                .read_text(encoding="utf-8")
            )
            self.assertEqual(result["findings"][0]["indicator"], "unverified")
            self.assertEqual(result["findings"][0]["error"], "IncompleteRead")
            self.assertEqual(result["findings"][1]["indicator"], "none")


class EvidenceWriteTests(unittest.TestCase):
    def test_atomic_write_replaces_complete_artifact_and_leaves_no_temp_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "run.json"
            path.write_text('{"stale": true}\n', encoding="utf-8")

            worker.write_json_atomic(path, {"complete": True, "findings": []})

            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                {"complete": True, "findings": []},
            )
            self.assertEqual(list(path.parent.glob(".run.json.*.tmp")), [])

    def test_interrupted_serialization_preserves_previous_complete_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "run.json"
            previous = '{"complete": true, "run_id": "previous"}\n'
            path.write_text(previous, encoding="utf-8")

            def interrupt(_payload, handle, **_kwargs):
                handle.write('{"complete":')
                raise RuntimeError("simulated interruption")

            with mock.patch.object(worker.json, "dump", side_effect=interrupt):
                with self.assertRaisesRegex(RuntimeError, "simulated interruption"):
                    worker.write_json_atomic(path, {"complete": True})

            self.assertEqual(path.read_text(encoding="utf-8"), previous)
            self.assertEqual(list(path.parent.glob(".run.json.*.tmp")), [])

if __name__ == "__main__":
    unittest.main()




