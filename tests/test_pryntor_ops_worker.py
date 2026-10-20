import importlib.util
import io
import json
import pathlib
import unittest
import urllib.error


MODULE_PATH = pathlib.Path(__file__).with_name("worker.py")
SPEC = importlib.util.spec_from_file_location("pryntor_ops_worker", MODULE_PATH)
worker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(worker)


class FakeResponse(io.BytesIO):
    status = 200


class StatusPayloadTests(unittest.TestCase):
    def test_accepts_complete_statuspage_payload(self):
        raw = json.dumps({"status": {"indicator": "none", "description": "All Systems Operational"}}).encode()
        self.assertEqual(worker.parse_status_payload(raw), ("none", "All Systems Operational"))

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

    def test_rejects_oversized_body_before_json_parse(self):
        response = FakeResponse(b"{" + b" " * worker.MAX_PROVIDER_BODY_BYTES)
        with self.assertRaisesRegex(worker.StatusPayloadError, "oversized_body"):
            worker.read_bounded_body(response)

    def test_records_http_status_for_invalid_error_response(self):
        response = urllib.error.HTTPError(
            "https://status.example/api", 404, "Not Found", {}, io.BytesIO(b"<html>not json</html>")
        )
        item = {}
        worker.record_response(item, response)
        self.assertEqual(item, {
            "http_status": 404,
            "indicator": "unverified",
            "error": "invalid_json",
            "evidence_type": "invalid_provider_payload",
        })

    def test_records_oversized_provider_body(self):
        item = {}
        worker.record_response(item, FakeResponse(b"x" * (worker.MAX_PROVIDER_BODY_BYTES + 1)))
        self.assertEqual(item["http_status"], 200)
        self.assertEqual(item["indicator"], "unverified")
        self.assertEqual(item["error"], "oversized_body")
        self.assertEqual(item["evidence_type"], "invalid_provider_payload")


if __name__ == "__main__":
    unittest.main()
