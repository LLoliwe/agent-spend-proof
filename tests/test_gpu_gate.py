import unittest
from scripts.verify_gpu_gate import check

GOOD = """docs/GPU_COST_GATE.md
read-only
No self-hosting or billing
PRY-223 total cost per successful run"""

class GateTests(unittest.TestCase):
    def test_valid(self):
        self.assertTrue(all(check(GOOD).values()))
    def test_missing_canonical(self):
        self.assertFalse(check(GOOD.replace("docs/GPU_COST_GATE.md", "elsewhere"))["canonical"])
    def test_missing_read_only(self):
        self.assertFalse(check(GOOD.replace("read-only", "editable"))["read_only"])
    def test_missing_spend_guard(self):
        self.assertFalse(check(GOOD.replace("No self-hosting", "self-hosting allowed"))["no_spend"])
    def test_missing_evidence(self):
        self.assertFalse(check(GOOD.replace("PRY-223", "unknown"))["evidence"])

if __name__ == "__main__":
    unittest.main()
