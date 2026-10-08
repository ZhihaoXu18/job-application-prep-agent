"""检查合成测试素材是否满足输入约束。"""

import unittest

from job_agent import read_resume
from tests.job_agent.support import FIXTURES, fixture


class FixtureChecks(unittest.TestCase):
    def test_resume_fixture_is_accepted(self):
        resume = read_resume(FIXTURES / "synthetic_resume.md")
        self.assertIn("This resume is a synthetic test fixture", resume)

    def test_job_fixtures_are_long_enough_for_cli_validation(self):
        names = (
            "job_explicit_eight_months.txt",
            "job_four_months_only.txt",
            "job_four_or_eight_months.txt",
            "job_term_unstated.txt",
        )
        for name in names:
            with self.subTest(name=name):
                self.assertGreaterEqual(len(fixture(name).strip()), 300)
