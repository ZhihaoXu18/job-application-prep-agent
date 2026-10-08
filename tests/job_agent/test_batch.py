"""批处理、去重和部分失败处理：模型与网页请求均被替换。"""

import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from job_agent import (
    already_tracked,
    canonical_url,
    job_id_for_source,
    load_batch_source,
    main,
    read_batch_sources,
    read_tracker,
)
from tests.job_agent.support import FIXTURES, build_test_analysis, fixture


class BatchChecks(unittest.TestCase):
    def test_batch_manifest_ignores_comments_and_blank_lines(self):
        sources = read_batch_sources(FIXTURES / "batch_jobs.txt")
        self.assertEqual(len(sources), 4)
        self.assertEqual(sources[0], "job_explicit_eight_months.txt")

    def test_empty_batch_manifest_is_rejected(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "batch.txt"
            path.write_text("\n# no jobs yet\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "contains no job sources"):
                read_batch_sources(path)

    def test_relative_batch_path_is_resolved_from_manifest(self):
        posting, source, url = load_batch_source(
            "job_four_months_only.txt",
            FIXTURES / "batch_jobs.txt",
        )
        self.assertIn("4-month internship", posting)
        self.assertEqual(Path(source), FIXTURES / "job_four_months_only.txt")
        self.assertIsNone(url)

    def test_batch_url_uses_web_fetcher(self):
        url = "https://employer.example/jobs/123"
        expected = fixture("job_explicit_eight_months.txt")
        with patch("job_agent.fetch_job", return_value=expected) as mocked:
            posting, source, identity_url = load_batch_source(url, FIXTURES / "batch_jobs.txt")
        self.assertEqual(posting, expected)
        self.assertEqual(source, url)
        self.assertEqual(identity_url, url)
        mocked.assert_called_once_with(url)

    def test_offline_batch_cli_prepares_all_fixture_jobs(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            argv = [
                "job_agent.py",
                "--resume", str(FIXTURES / "synthetic_resume.md"),
                "--profile", "profile.example.json",
                "--batch-file", str(FIXTURES / "batch_jobs.txt"),
                "--out", str(output),
            ]
            stdout = StringIO()
            with (
                patch("sys.argv", argv),
                patch(
                    "job_agent.make_analysis",
                    side_effect=lambda *_: build_test_analysis("", "variable_or_unclear"),
                ) as mocked,
                redirect_stdout(stdout),
            ):
                self.assertEqual(main(), 0)

            self.assertEqual(mocked.call_count, 4)
            self.assertEqual(len(list(output.glob("*.md"))), 5)
            self.assertEqual(len(read_tracker(output / "applications.csv")), 4)
            self.assertIn("Batch complete: 4 prepared, 0 duplicates, 0 failed.", stdout.getvalue())
            self.assertIn("# Batch review queue", (output / "priority_queue.md").read_text())

    def test_batch_continues_after_one_source_fails(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "output"
            manifest = root / "batch.txt"
            manifest.write_text(
                f"{FIXTURES / 'job_term_unstated.txt'}\nmissing-posting.txt\n",
                encoding="utf-8",
            )
            argv = [
                "job_agent.py",
                "--resume", str(FIXTURES / "synthetic_resume.md"),
                "--batch-file", str(manifest),
                "--out", str(output),
            ]
            stdout = StringIO()
            stderr = StringIO()
            with (
                patch("sys.argv", argv),
                patch(
                    "job_agent.make_analysis",
                    side_effect=lambda *_: build_test_analysis("", "variable_or_unclear"),
                ) as mocked,
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                self.assertEqual(main(), 1)

            self.assertEqual(mocked.call_count, 1)
            self.assertEqual(len(read_tracker(output / "applications.csv")), 1)
            self.assertIn("Batch complete: 1 prepared, 0 duplicates, 1 failed.", stdout.getvalue())
            self.assertIn("Skipped missing-posting.txt", stderr.getvalue())
            self.assertIn("Job ID:", (output / "priority_queue.md").read_text())

    def test_batch_deduplicates_repeated_urls_before_fetch_and_model(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "batch.txt"
            manifest.write_text(
                "https://employer.example/jobs?jobId=123&utm_source=mail\n"
                "https://employer.example/jobs?jobId=123#apply\n",
                encoding="utf-8",
            )
            output = root / "output"
            argv = ["job_agent.py", "--resume", str(FIXTURES / "synthetic_resume.md"),
                    "--batch-file", str(manifest), "--out", str(output)]
            with (
                patch("sys.argv", argv),
                patch("job_agent.fetch_job", return_value=fixture("job_explicit_eight_months.txt")) as fetched,
                patch("job_agent.make_analysis", return_value=build_test_analysis("")) as analyzed,
                redirect_stdout(StringIO()),
            ):
                self.assertEqual(main(), 0)
            self.assertEqual(fetched.call_count, 1)
            self.assertEqual(analyzed.call_count, 1)
            self.assertEqual(len(read_tracker(output / "applications.csv")), 1)
            with (
                patch("sys.argv", argv),
                patch("job_agent.fetch_job") as fetched_again,
                patch("job_agent.make_analysis") as analyzed_again,
                redirect_stdout(StringIO()),
            ):
                self.assertEqual(main(), 0)
            fetched_again.assert_not_called()
            analyzed_again.assert_not_called()
            self.assertIn("No new jobs", (output / "priority_queue.md").read_text())

    def test_batch_deduplicates_equal_posting_text_at_different_paths(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            posting = fixture("job_term_unstated.txt")
            (root / "one.txt").write_text(posting, encoding="utf-8")
            (root / "two.txt").write_text("  " + posting + "\n", encoding="utf-8")
            manifest = root / "batch.txt"
            manifest.write_text("one.txt\ntwo.txt\n", encoding="utf-8")
            argv = ["job_agent.py", "--resume", str(FIXTURES / "synthetic_resume.md"),
                    "--batch-file", str(manifest), "--out", str(root / "output")]
            stdout = StringIO()
            with (
                patch("sys.argv", argv),
                patch("job_agent.make_analysis", return_value=build_test_analysis("")) as analyzed,
                redirect_stdout(stdout),
            ):
                self.assertEqual(main(), 0)
            analyzed.assert_called_once()
            self.assertIn("1 prepared, 1 duplicates, 0 failed", stdout.getvalue())

    def test_content_fingerprint_skips_same_posting_on_later_batch(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            posting = fixture("job_term_unstated.txt")
            (root / "one.txt").write_text(posting, encoding="utf-8")
            (root / "two.txt").write_text("  " + posting + "\n", encoding="utf-8")
            manifest = root / "batch.txt"
            output = root / "output"
            argv = ["job_agent.py", "--resume", str(FIXTURES / "synthetic_resume.md"),
                    "--batch-file", str(manifest), "--out", str(output)]
            with (
                patch("sys.argv", argv),
                patch("job_agent.make_analysis", return_value=build_test_analysis("")) as analyzed,
                redirect_stdout(StringIO()),
            ):
                manifest.write_text("one.txt\n", encoding="utf-8")
                self.assertEqual(main(), 0)
                manifest.write_text("two.txt\n", encoding="utf-8")
                self.assertEqual(main(), 0)
            analyzed.assert_called_once()
            rows = read_tracker(output / "applications.csv")
            self.assertEqual(len(rows), 1)
            self.assertTrue(rows[0]["content_fingerprint"])

    def test_distinct_job_identity_query_parameters_do_not_collide(self):
        first = "https://employer.example/jobs?jobId=123&utm_source=mail"
        second = "https://employer.example/jobs?jobId=456&utm_source=mail"
        self.assertNotEqual(canonical_url(first), canonical_url(second))
        self.assertNotEqual(job_id_for_source(first), job_id_for_source(second))

    def test_older_tracker_url_is_recognized_after_url_identity_change(self):
        url = "https://employer.example/jobs?jobId=123&utm_source=mail"
        old_id = job_id_for_source("https://employer.example/jobs")
        self.assertTrue(already_tracked([{"job_id": old_id, "url": url}], job_id_for_source(url), url))
