import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from gpu_workload_screen import evaluate, illustrative_rates

JOBS = json.loads((ROOT / "docs/gpu_workloads_2026-10-17.json").read_text())
QUOTES = json.loads((ROOT / "docs/gpu_quotes_2026-10-17.json").read_text())

class TestGPUWorkloadScreen(unittest.TestCase):
    def test_three_real_projects(self):
        self.assertEqual([x["issue"] for x in evaluate(JOBS)["workloads"]],
                         ["PRY-182","PRY-191","PRY-170"])
    def test_no_spend_or_savings(self):
        r = evaluate(JOBS)
        self.assertEqual(r["purchases_initiated"], 0)
        self.assertEqual(r["savings_claim"], "NONE")
        self.assertTrue(all(x["historical_realized_savings_usd"] is None for x in r["workloads"]))
    def test_cpu_first_on_two_jobs(self):
        self.assertEqual([x["decision"] for x in evaluate(JOBS)["workloads"]][:2],
                         ["CPU_FIRST_NO_GPU_PURCHASE"] * 2)
    def test_framezero_unproven(self):
        self.assertEqual(evaluate(JOBS)["workloads"][2]["decision"], "GPU_CANDIDATE_HOLD")
    def test_missing_evidence_not_approved(self):
        self.assertTrue(all(x["missing_gates"] and not x["buy_authorized"]
                            for x in evaluate(JOBS)["workloads"]))
    def test_refuse_fabricated_paid_baseline(self):
        data = copy.deepcopy(JOBS); data["historical_paid_gpu"] = True
        with self.assertRaises(ValueError): evaluate(data)
    def test_refuse_duplicate_issue(self):
        data = copy.deepcopy(JOBS); data["workloads"][2]["issue"] = "PRY-191"
        with self.assertRaises(ValueError): evaluate(data)
    def test_refuse_gpu_needed_without_proof(self):
        data = copy.deepcopy(JOBS); data["workloads"][0]["gpu_required"] = True
        with self.assertRaises(ValueError): evaluate(data)
    def test_refuse_future_gpu_claim(self):
        data = copy.deepcopy(JOBS); data["workloads"][2]["gpu_required"] = True
        with self.assertRaises(ValueError): evaluate(data)
    def test_refuse_missing_boolean(self):
        data = copy.deepcopy(JOBS); del data["workloads"][2]["gates"]["output_qa_confirmed"]
        with self.assertRaises(ValueError): evaluate(data)
    def test_refuse_truthy_string(self):
        data = copy.deepcopy(JOBS); data["workloads"][0]["gates"]["rights_and_data_clear"] = "yes"
        with self.assertRaises(ValueError): evaluate(data)
    def test_illustrations_are_not_savings(self):
        v = illustrative_rates(QUOTES, 15)
        self.assertEqual([x["hypothetical_gpu_only_usd"] for x in v],
                         ["0.067500","0.125000","0.222500","0.275400"])
        self.assertTrue(all(x["realized_savings_usd"] is None for x in v))
    def test_refuse_zero_rate(self):
        q = copy.deepcopy(QUOTES); q[0]["gpu_only_usd_per_hour"] = 0
        with self.assertRaises(ValueError): illustrative_rates(q, 15)
    def test_refuse_nan_rate(self):
        q = copy.deepcopy(QUOTES); q[0]["gpu_only_usd_per_hour"] = "NaN"
        with self.assertRaises(ValueError): illustrative_rates(q, 15)
    def test_refuse_missing_provenance(self):
        q = copy.deepcopy(QUOTES); del q[0]["source_url"]
        with self.assertRaises(ValueError): illustrative_rates(q, 15)
    def test_refuse_fake_checkout(self):
        q = copy.deepcopy(QUOTES); q[0]["rate_class"] = "CHECKOUT_VERIFIED"
        with self.assertRaises(ValueError): illustrative_rates(q, 15)
    def test_refuse_bad_minutes(self):
        for m in [0,-1,1441,"NaN"]:
            with self.subTest(m=m), self.assertRaises(ValueError):
                illustrative_rates(QUOTES, m)

if __name__ == "__main__":
    unittest.main()
