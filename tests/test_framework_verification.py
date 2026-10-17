"""Regression checks for false-positive framework installation reports."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "verify_frameworks",
    Path(__file__).resolve().parents[1] / "pryntor-ops/frameworks/verify_frameworks.py",
)
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


class FrameworkVerificationTests(unittest.TestCase):
    def test_openhands_checks_agent_sdk_distribution_and_import(self):
        with patch.object(verifier.importlib.metadata, "version", return_value="1.0") as version:
            with patch.object(verifier.importlib, "import_module") as imported:
                result = verifier.verify("openhands")
        version.assert_called_once_with("openhands-sdk")
        imported.assert_called_once_with("openhands.sdk")
        self.assertTrue(result["verified"])
        self.assertFalse(result["live_agent"])
        self.assertEqual(result["model_calls"], 0)

    def test_present_metadata_does_not_hide_broken_import(self):
        with patch.object(verifier.importlib.metadata, "version", return_value="1.0"):
            with patch.object(verifier.importlib, "import_module", side_effect=ImportError("private detail")):
                result = verifier.verify("crewai")
        self.assertFalse(result["verified"])
        self.assertEqual(result["error_type"], "ImportError")
        self.assertNotIn("private detail", str(result))

    def test_missing_distribution_fails_before_import(self):
        with patch.object(verifier.importlib.metadata, "version", side_effect=verifier.importlib.metadata.PackageNotFoundError):
            with patch.object(verifier.importlib, "import_module") as imported:
                result = verifier.verify("langgraph")
        imported.assert_not_called()
        self.assertFalse(result["verified"])

    def test_cli_returns_failure_for_broken_installation(self):
        with patch("sys.argv", ["verify_frameworks.py", "microsoft"]):
            with patch.object(verifier.importlib.metadata, "version", side_effect=verifier.importlib.metadata.PackageNotFoundError):
                with patch("builtins.print") as output:
                    self.assertEqual(verifier.main(), 1)
        self.assertIn('"verified": false', output.call_args.args[0])
