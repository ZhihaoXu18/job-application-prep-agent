"""单职位输出与人工提交边界：只在临时目录写入合成结果。"""

import json
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from job_agent import (
    CandidateProfile,
    canonical_url,
    check_analysis,
    main,
    read_tracker,
    render_packet,
)
from tests.job_agent.support import FIXTURES, build_test_analysis, fixture


class OutputChecks(unittest.TestCase):
    def test_packet_keeps_human_review_boundary_visible(self):
        resume = fixture("synthetic_resume.md")
        posting = fixture("job_explicit_eight_months.txt")
        quote = "Work term: January 4 to August 27, 2027 (8 months)."
        a = check_analysis(build_test_analysis(quote), resume, posting)
        packet = render_packet(a, resume, posting, "fixture://explicit-eight", "2026-09-29")
        self.assertIn("Prepared only; application not submitted", packet)
        self.assertIn("submit the application yourself", packet)

    def test_canonical_url_ignores_tracking_and_fragment(self):
        first = canonical_url("HTTPS://Example.COM/jobs/123/?utm_source=test#apply")
        second = canonical_url("https://example.com/jobs/123")
        self.assertEqual(first, second)

    def test_offline_cli_writes_packet_and_tracker_with_profile(self):
        resume_path = FIXTURES / "synthetic_resume.md"
        posting_path = FIXTURES / "job_explicit_eight_months.txt"
        quote = "Work term: January 4 to August 27, 2027 (8 months)."
        with TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            argv = [
                "job_agent.py",
                "--resume", str(resume_path),
                "--profile", "profile.example.json",
                "--job-file", str(posting_path),
                "--out", str(output),
            ]
            with (
                patch("sys.argv", argv),
                patch("job_agent.make_analysis", return_value=build_test_analysis(quote)) as mocked,
                redirect_stdout(StringIO()),
            ):
                self.assertEqual(main(), 0)

            self.assertEqual(mocked.call_count, 1)
            passed_profile = mocked.call_args.args[3]
            self.assertEqual(passed_profile.preferences.desired_term, "8 months")
            packets = list(output.glob("*.md"))
            self.assertEqual(len(packets), 1)
            self.assertTrue((output / "applications.csv").exists())
            self.assertIn("application not submitted", packets[0].read_text(encoding="utf-8"))

    def test_offline_cli_without_profile_uses_empty_profile(self):
        with TemporaryDirectory() as directory:
            argv = [
                "job_agent.py",
                "--resume", str(FIXTURES / "synthetic_resume.md"),
                "--job-file", str(FIXTURES / "job_term_unstated.txt"),
                "--out", str(Path(directory) / "output"),
            ]
            with (
                patch("sys.argv", argv),
                patch(
                    "job_agent.make_analysis",
                    return_value=build_test_analysis("", "variable_or_unclear"),
                ) as mocked,
                redirect_stdout(StringIO()),
            ):
                self.assertEqual(main(), 0)
            self.assertEqual(mocked.call_args.args[3], CandidateProfile())

    def test_single_job_rerun_preserves_feedback_and_avoids_model_call(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            argv = [
                "job_agent.py", "--resume", str(FIXTURES / "synthetic_resume.md"),
                "--job-file", str(FIXTURES / "job_term_unstated.txt"), "--out", str(output),
            ]
            with (
                patch("sys.argv", argv),
                patch("job_agent.make_analysis", return_value=build_test_analysis("")) as analyzed,
                redirect_stdout(StringIO()),
            ):
                self.assertEqual(main(), 0)
            analyzed.assert_called_once()
            job_id = read_tracker(output / "applications.csv")[0]["job_id"]
            with (
                patch("sys.argv", ["job_agent.py", "--feedback-job-id", job_id,
                                   "--outcome", "applied", "--out", str(output)]),
                redirect_stdout(StringIO()),
            ):
                self.assertEqual(main(), 0)
            with (
                patch("sys.argv", argv),
                patch("job_agent.make_analysis") as analyzed_again,
                redirect_stdout(StringIO()),
            ):
                self.assertEqual(main(), 0)
            analyzed_again.assert_not_called()
            rows = read_tracker(output / "applications.csv")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["status"], "applied")
            history = json.loads(rows[0]["status_history"])
            self.assertEqual([event["to"] for event in history], ["prepared", "applied"])
            self.assertEqual(history[-1]["source"], "cli")
