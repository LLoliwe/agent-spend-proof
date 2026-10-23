import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).parents[1]
SCOPED_WORKFLOWS = (
    ROOT / ".github" / "workflows" / "test.yml",
    ROOT / ".github" / "workflows" / "pryntor-ops-worker.yml",
)
ACTION_REFERENCE = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)", re.MULTILINE)
FULL_COMMIT = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")


class WorkflowActionPinTests(unittest.TestCase):
    def test_status_worker_workflows_pin_actions_to_full_commits(self):
        found = []
        for workflow in SCOPED_WORKFLOWS:
            references = ACTION_REFERENCE.findall(workflow.read_text(encoding="utf-8"))
            self.assertTrue(references, f"no action references found in {workflow}")
            found.extend((workflow.name, reference) for reference in references)

        unpinned = [
            f"{workflow}: {reference}"
            for workflow, reference in found
            if not FULL_COMMIT.fullmatch(reference)
        ]
        self.assertFalse(unpinned, "moving action references: " + ", ".join(unpinned))

    def test_expected_status_worker_actions_remain_covered(self):
        references = {
            reference.split("@", 1)[0]
            for workflow in SCOPED_WORKFLOWS
            for reference in ACTION_REFERENCE.findall(workflow.read_text(encoding="utf-8"))
        }
        self.assertEqual(references, {
            "actions/checkout",
            "actions/setup-python",
            "actions/upload-artifact",
        })


if __name__ == "__main__":
    unittest.main()
