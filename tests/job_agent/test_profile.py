"""候选人偏好与经历证据输入校验：不调用模型。"""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from job_agent import CandidateProfile, analysis_messages, read_profile
from tests.job_agent.support import fixture


class ProfileChecks(unittest.TestCase):
    def test_example_profile_is_supported_by_synthetic_resume(self):
        profile = read_profile(Path("profile.example.json"), fixture("synthetic_resume.md"))
        self.assertEqual(profile.preferences.desired_term, "8 months")
        self.assertEqual(len(profile.experience_bank), 3)

    def test_missing_optional_profile_uses_empty_defaults(self):
        profile = read_profile(None, fixture("synthetic_resume.md"))
        self.assertEqual(profile, CandidateProfile())

    def test_profile_rejects_evidence_missing_from_resume(self):
        data = json.loads(Path("profile.example.json").read_text(encoding="utf-8"))
        data["experience_bank"][0]["source_resume_quote"] = "Managed a team of 50 people."
        with TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not supported"):
                read_profile(path, fixture("synthetic_resume.md"))

    def test_profile_rejects_duplicate_evidence_ids(self):
        data = json.loads(Path("profile.example.json").read_text(encoding="utf-8"))
        data["experience_bank"][1]["id"] = data["experience_bank"][0]["id"]
        with TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicated"):
                read_profile(path, fixture("synthetic_resume.md"))

    def test_profile_rejects_unknown_fields(self):
        data = json.loads(Path("profile.example.json").read_text(encoding="utf-8"))
        data["automatic_submission"] = True
        with TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "could not be read or validated"):
                read_profile(path, fixture("synthetic_resume.md"))

    def test_analysis_messages_include_profile_without_hardcoded_candidate(self):
        resume = fixture("synthetic_resume.md")
        profile = read_profile(Path("profile.example.json"), resume)
        messages = analysis_messages(
            resume,
            fixture("job_explicit_eight_months.txt"),
            "fixture",
            profile,
        )
        self.assertIn("power-bi-reporting", messages[1]["content"])
        self.assertIn("Toronto, Ontario", messages[1]["content"])
        self.assertNotIn("Consider Waterloo Statistics", messages[0]["content"])
