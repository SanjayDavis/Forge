"""Tests for the BharatCode-backed Forge planner (optional package)."""

import json
import os
import unittest
from unittest.mock import patch

try:
    from forge.bharatcode import BharatCodePlanner, BharatCodeError
    from forge.bharatcode._http import chat_completion
    _AVAILABLE = True
except Exception:  # pragma: no cover
    _AVAILABLE = False


@unittest.skipUnless(_AVAILABLE, "forge-bharatcode not installed")
class TestBharatCodePlanner(unittest.TestCase):
    def _valid_proposal(self):
        return {
            "proposal_id": "prop_demo_1234",
            "reason": "demo",
            "confidence": 0.8,
            "events": [
                {"op": "task_created", "id": "demo", "title": "Demo",
                 "description": "", "acceptance": [], "files": [], "notes": [],
                 "priority": "medium"},
                {"op": "task_expanded", "task": "demo",
                 "children": [
                     {"id": "demo-foundation", "title": "Demo — Foundation",
                      "description": "", "acceptance": [], "files": [], "priority": "medium"},
                     {"id": "demo-core", "title": "Demo — Core",
                      "description": "", "acceptance": [], "files": [], "priority": "medium"},
                 ]},
                {"op": "dependency_added", "task": "demo-core", "depends_on": "demo-foundation"},
            ],
        }

    @patch("forge.bharatcode.planner.chat_completion")
    def test_plan_parses_and_validates(self, mock_chat):
        mock_chat.return_value = json.dumps(self._valid_proposal())
        planner = BharatCodePlanner(api_key="test-key")
        proposal = planner.plan("Build a demo", priority="high")
        self.assertEqual(proposal["proposal_id"], "prop_demo_1234")
        # model-provided priority is preserved
        self.assertEqual(proposal["events"][0]["priority"], "medium")
        from forge import validate_proposal
        validate_proposal(proposal)  # must not raise

    @patch("forge.bharatcode.planner.chat_completion")
    def test_plan_handles_code_fences(self, mock_chat):
        mock_chat.return_value = "```json\n" + json.dumps(self._valid_proposal()) + "\n```"
        planner = BharatCodePlanner(api_key="test-key")
        proposal = planner.plan("Build a demo")
        self.assertIn("events", proposal)

    @patch("forge.bharatcode.planner.chat_completion")
    def test_plan_raises_on_bad_json(self, mock_chat):
        mock_chat.return_value = "not json at all"
        planner = BharatCodePlanner(api_key="test-key")
        from forge import ProposalError
        with self.assertRaises(ProposalError):
            planner.plan("Build a demo")

    def test_missing_key_raises(self):
        os.environ.pop("BHARATCODE_API_KEY", None)
        planner = BharatCodePlanner()  # no key
        with self.assertRaises(BharatCodeError):
            planner.plan("Build a demo")

    def test_normalizes_aliases(self):
        alias_proposal = {
            "proposal_id": "prop_alias",
            "reason": "r",
            "confidence": 0.9,
            "events": [
                {"type": "task_created", "task": {"id": "root", "title": "Root",
                 "description": "", "acceptance": [], "files": [], "notes": [],
                 "priority": "medium"}},
                {"type": "task_expanded", "task": "root",
                 "children": [{"id": "c1", "title": "C1", "description": "",
                               "acceptance": [], "files": [], "priority": "medium"}]},
            ],
        }
        with patch("forge.bharatcode.planner.chat_completion",
                   return_value=__import__("json").dumps(alias_proposal)):
            planner = BharatCodePlanner(api_key="test-key")
            proposal = planner.plan("Root")
        self.assertEqual(proposal["events"][0]["op"], "task_created")
        self.assertEqual(proposal["events"][0]["id"], "root")
        self.assertEqual(proposal["events"][1]["task"], "root")

    def test_commit_without_client_raises(self):
        planner = BharatCodePlanner(api_key="test-key")
        with self.assertRaises(Exception):
            planner.commit({"proposal_id": "x", "reason": "r", "confidence": 0.5, "events": [
                {"op": "task_created", "id": "t", "title": "T", "description": "",
                 "acceptance": [], "files": [], "notes": [], "priority": "medium"}]})


if __name__ == "__main__":
    unittest.main()
