import importlib.util
import io
import json
import pathlib
import unittest
import urllib.error
import urllib.request


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


if __name__ == "__main__":
    unittest.main()


