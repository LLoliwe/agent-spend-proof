import importlib.util
import json
import pathlib
import unittest


MODULE_PATH = pathlib.Path(__file__).parents[1] / "pryntor-ops" / "worker.py"
if not MODULE_PATH.exists():
    MODULE_PATH = pathlib.Path(__file__).with_name("worker.py")
SPEC = importlib.util.spec_from_file_location("pryntor_ops_worker", MODULE_PATH)
worker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(worker)


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


if __name__ == "__main__":
    unittest.main()
