"""排序分数与引用日期测试：分数不表示录用概率或岗位仍开放。"""

import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from job_agent import (
    CandidateProfile,
    Fact,
    PreparedJob,
    ProfilePreferences,
    quoted_date,
    rank_job,
    write_priority_queue,
)
from tests.job_agent.support import build_test_analysis


class RankingChecks(unittest.TestCase):
    def test_rank_uses_supported_terms_preferences_and_quoted_dates(self):
        a = build_test_analysis("Work term: 8 months.")
        a.deadline = Fact(value="October 8, 2026", source_quote="Apply by October 8, 2026.")
        a.publication_date = Fact(value="October 1, 2026", source_quote="Posted October 1, 2026.")
        a.location = Fact(value="Toronto, Ontario", source_quote="Location: Toronto, Ontario")
        a.work_mode = Fact(value="Hybrid", source_quote="Work mode: Hybrid")
        profile = CandidateProfile(preferences=ProfilePreferences(
            target_roles=["Data Analyst"], preferred_locations=["Toronto"],
            preferred_work_modes=["Hybrid"], desired_term="8 months",
        ))
        job = PreparedJob("abc", Path("packet.md"), "synthetic job", a, title_supported=True)
        score, reasons = rank_job(job, profile, date(2026, 10, 3))
        self.assertEqual(score, 95)
        self.assertIn("employer-quoted publication within 14 days (+5)", reasons)

    def test_unknown_and_ambiguous_dates_do_not_get_recency_points(self):
        a = build_test_analysis("", "variable_or_unclear")
        a.deadline = Fact(value="2026-10-10", source_quote="October 10, 2026 or October 20, 2026")
        a.publication_date = Fact(value="Not stated", source_quote="")
        self.assertIsNone(quoted_date(a.deadline))
        job = PreparedJob("abc", Path("packet.md"), "synthetic job", a)
        score, reasons = rank_job(job, CandidateProfile(), date(2026, 10, 3))
        self.assertEqual(score, 0)
        self.assertIn("employer publication date unknown (+0)", reasons)

    def test_past_deadline_is_not_called_closed(self):
        a = build_test_analysis("", "variable_or_unclear")
        a.deadline = Fact(value="2026-09-30", source_quote="Deadline: 2026-09-30")
        job = PreparedJob("abc", Path("packet.md"), "synthetic job", a)
        score, reasons = rank_job(job, CandidateProfile(), date(2026, 10, 3))
        self.assertEqual(score, -20)
        self.assertTrue(any("verify live status" in reason for reason in reasons))

    def test_queue_orders_new_jobs_by_score(self):
        strong = build_test_analysis("8 months")
        weak = build_test_analysis("", "variable_or_unclear")
        profile = CandidateProfile(preferences=ProfilePreferences(desired_term="8 months"))
        jobs = [
            PreparedJob("weak", Path("weak.md"), "synthetic weak", weak),
            PreparedJob("strong", Path("strong.md"), "synthetic strong", strong),
        ]
        with TemporaryDirectory() as directory:
            content = write_priority_queue(Path(directory), jobs, profile).read_text()
        self.assertLess(content.index("Job ID: strong"), content.index("Job ID: weak"))

    def test_full_september_name_parses_without_truncation(self):
        self.assertEqual(
            quoted_date(Fact(value="September 30, 2026", source_quote="Posted September 30, 2026.")),
            date(2026, 9, 30),
        )
