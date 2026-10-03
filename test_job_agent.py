import unittest
import json
from datetime import date
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import requests

from job_agent import (
    Analysis,
    BulletEdit,
    CandidateProfile,
    Fact,
    PreparedJob,
    ProfilePreferences,
    already_tracked,
    analysis_messages,
    canonical_url,
    check_analysis,
    fetch_job,
    load_batch_source,
    main,
    job_id_for_source,
    quoted_date,
    rank_job,
    write_priority_queue,
    read_batch_sources,
    read_profile,
    read_resume,
    read_tracker,
    render_packet,
)


FIXTURES = Path(__file__).parent / "tests" / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def html_response(
    html: str,
    *,
    url: str = "https://employer.example/jobs/123",
    content_type: str = "text/html; charset=utf-8",
    content_length: str | None = None,
) -> Mock:
    response = Mock()
    response.url = url
    response.text = html
    response.content = html.encode("utf-8")
    response.headers = {"Content-Type": content_type}
    if content_length is not None:
        response.headers["Content-Length"] = content_length
    response.raise_for_status.return_value = None
    return response


def make_analysis(
    term_quote: str,
    classification: str = "8_month_confirmed",
    *,
    original_bullet: str = "Built Power BI reports for a fictional campus operations dataset.",
    revised_bullet: str = "Built Power BI reports for a fictional campus operations dataset.",
) -> Analysis:
    unknown = Fact(value="Not stated", source_quote="")
    return Analysis(
        employer="Northstar Analytics", title="Data Analyst Co-op", location=unknown.model_copy(),
        term=Fact(value=term_quote, source_quote=term_quote),
        start_date=unknown.model_copy(), deadline=unknown.model_copy(),
        publication_date=unknown.model_copy(), work_mode=unknown.model_copy(),
        term_classification=classification, priority="high",
        matching_points=[], gaps=[], resume_edits=[
            BulletEdit(
                original=original_bullet,
                revised=revised_bullet,
                reason="Reporting fit",
            )
        ],
        application_paragraph="", user_actions=[],
    )


class EvidenceChecks(unittest.TestCase):
    def test_explicit_eight_month_term(self):
        resume = fixture("synthetic_resume.md")
        posting = fixture("job_explicit_eight_months.txt")
        quote = "Work term: January 4 to August 27, 2027 (8 months)."
        a = check_analysis(
            make_analysis(quote),
            resume,
            posting,
        )
        self.assertEqual(a.term_classification, "8_month_confirmed")
        self.assertEqual(len(a.resume_edits), 1)

    def test_four_month_only_is_low_priority(self):
        posting = fixture("job_four_months_only.txt")
        quote = "This is a 4-month internship from January 4 to April 30, 2027."
        a = check_analysis(make_analysis(quote), fixture("synthetic_resume.md"), posting)
        self.assertEqual(a.term_classification, "4_month_only")
        self.assertEqual(a.priority, "low")

    def test_four_or_eight_requires_confirmation(self):
        posting = fixture("job_four_or_eight_months.txt")
        quote = "Candidates may choose a 4-month or 8-month work term beginning January 2027."
        a = check_analysis(make_analysis(quote), fixture("synthetic_resume.md"), posting)
        self.assertEqual(a.term_classification, "variable_or_unclear")
        self.assertTrue(any("Confirm" in action for action in a.user_actions))

    def test_unstated_term_remains_unknown(self):
        a = check_analysis(
            make_analysis("", "variable_or_unclear"),
            fixture("synthetic_resume.md"),
            fixture("job_term_unstated.txt"),
        )
        self.assertEqual(a.term.value, "Not stated")
        self.assertEqual(a.term.source_quote, "")
        self.assertEqual(a.term_classification, "variable_or_unclear")

    def test_unsupported_quote_cannot_confirm_eight_months(self):
        a = check_analysis(
            make_analysis("8 months"),
            fixture("synthetic_resume.md"),
            fixture("job_term_unstated.txt"),
        )
        self.assertEqual(a.term.value, "Not stated")
        self.assertEqual(a.term_classification, "variable_or_unclear")

    def test_unsupported_facts_are_reset_and_flagged(self):
        a = make_analysis("", "variable_or_unclear")
        a.location = Fact(value="Vancouver", source_quote="Location: Vancouver")
        a.deadline = Fact(value="Tomorrow", source_quote="Apply by tomorrow")
        checked = check_analysis(
            a,
            fixture("synthetic_resume.md"),
            fixture("job_term_unstated.txt"),
        )
        self.assertEqual(checked.location, Fact(value="Not stated", source_quote=""))
        self.assertEqual(checked.deadline, Fact(value="Not stated", source_quote=""))
        self.assertTrue(any("location" in action for action in checked.user_actions))
        self.assertTrue(any("deadline" in action for action in checked.user_actions))

    def test_supported_fact_allows_case_and_whitespace_differences(self):
        a = make_analysis("", "variable_or_unclear")
        a.location = Fact(
            value="Kitchener, Ontario",
            source_quote="LOCATION:   Kitchener, Ontario.",
        )
        checked = check_analysis(
            a,
            fixture("synthetic_resume.md"),
            fixture("job_term_unstated.txt"),
        )
        self.assertEqual(checked.location.value, "Kitchener, Ontario")

    def test_fabricated_original_resume_bullet_is_omitted(self):
        quote = "Work term: January 4 to August 27, 2027 (8 months)."
        a = check_analysis(
            make_analysis(quote, original_bullet="Increased revenue by 80%."),
            fixture("synthetic_resume.md"),
            fixture("job_explicit_eight_months.txt"),
        )
        self.assertFalse(a.resume_edits)
        self.assertTrue(any("omitted" in action for action in a.user_actions))

    def test_new_numeric_claim_in_rewrite_is_omitted(self):
        quote = "Work term: January 4 to August 27, 2027 (8 months)."
        a = check_analysis(
            make_analysis(
                quote,
                revised_bullet="Built Power BI reports and improved reporting efficiency by 80%.",
            ),
            fixture("synthetic_resume.md"),
            fixture("job_explicit_eight_months.txt"),
        )
        self.assertFalse(a.resume_edits)
        self.assertTrue(any("numeric claim" in action for action in a.user_actions))

    def test_existing_numeric_claim_can_be_preserved(self):
        quote = "Work term: January 4 to August 27, 2027 (8 months)."
        original = "Cleaned 25,000 synthetic survey rows with Python and documented validation checks."
        a = check_analysis(
            make_analysis(
                quote,
                original_bullet=original,
                revised_bullet="Cleaned and validated 25,000 synthetic survey rows with Python.",
            ),
            fixture("synthetic_resume.md"),
            fixture("job_explicit_eight_months.txt"),
        )
        self.assertEqual(len(a.resume_edits), 1)

    def test_deadline_value_conflicting_with_quote_is_reset(self):
        quote = "Work term: January 4 to August 27, 2027 (8 months)."
        a = make_analysis(quote)
        a.deadline = Fact(
            value="October 30, 2026",
            source_quote="Application deadline: October 15, 2026 at 5:00 p.m. Eastern.",
        )
        checked = check_analysis(
            a,
            fixture("synthetic_resume.md"),
            fixture("job_explicit_eight_months.txt"),
        )
        self.assertEqual(checked.deadline, Fact(value="Not stated", source_quote=""))
        self.assertTrue(any("deadline" in action and "conflicts" in action for action in checked.user_actions))

    def test_location_value_conflicting_with_quote_is_reset(self):
        a = make_analysis("", "variable_or_unclear")
        a.location = Fact(
            value="Vancouver, British Columbia",
            source_quote="Location: Kitchener, Ontario.",
        )
        checked = check_analysis(
            a,
            fixture("synthetic_resume.md"),
            fixture("job_term_unstated.txt"),
        )
        self.assertEqual(checked.location, Fact(value="Not stated", source_quote=""))
        self.assertTrue(any("location" in action and "conflicts" in action for action in checked.user_actions))

    def test_application_paragraph_with_unsupported_number_is_omitted(self):
        quote = "Work term: January 4 to August 27, 2027 (8 months)."
        a = make_analysis(quote)
        a.application_paragraph = "I improved reporting efficiency by 90%."
        checked = check_analysis(
            a,
            fixture("synthetic_resume.md"),
            fixture("job_explicit_eight_months.txt"),
        )
        self.assertEqual(checked.application_paragraph, "")
        self.assertTrue(any("application paragraph" in action for action in checked.user_actions))

    def test_application_paragraph_can_preserve_supported_number(self):
        quote = "Work term: January 4 to August 27, 2027 (8 months)."
        paragraph = "I cleaned 25,000 synthetic survey rows with Python."
        a = make_analysis(quote)
        a.application_paragraph = paragraph
        checked = check_analysis(
            a,
            fixture("synthetic_resume.md"),
            fixture("job_explicit_eight_months.txt"),
        )
        self.assertEqual(checked.application_paragraph, paragraph)

    def test_matching_point_with_unsupported_number_is_omitted(self):
        quote = "Work term: January 4 to August 27, 2027 (8 months)."
        a = make_analysis(quote)
        a.matching_points = ["Improved a reporting process by 99%."]
        checked = check_analysis(
            a,
            fixture("synthetic_resume.md"),
            fixture("job_explicit_eight_months.txt"),
        )
        self.assertFalse(checked.matching_points)
        self.assertTrue(any("matching point" in action for action in checked.user_actions))

    def test_gap_with_unsupported_numeric_requirement_is_omitted(self):
        quote = "Work term: January 4 to August 27, 2027 (8 months)."
        a = make_analysis(quote)
        a.gaps = ["The applicant lacks the required 7 years of experience."]
        checked = check_analysis(
            a,
            fixture("synthetic_resume.md"),
            fixture("job_explicit_eight_months.txt"),
        )
        self.assertFalse(checked.gaps)
        self.assertTrue(any("gap" in action for action in checked.user_actions))

    def test_analysis_rejects_invalid_closed_values(self):
        data = make_analysis("", "variable_or_unclear").model_dump()
        data["priority"] = "urgent"
        with self.assertRaises(ValueError):
            Analysis.model_validate(data)

        data = make_analysis("", "variable_or_unclear").model_dump()
        data["term_classification"] = "probably_eight_months"
        with self.assertRaises(ValueError):
            Analysis.model_validate(data)

    def test_spelled_and_numeric_term_values_are_equivalent(self):
        quote = "The eight-month placement begins in January."
        a = make_analysis(quote)
        a.term.value = "8 months"
        checked = check_analysis(a, fixture("synthetic_resume.md"), quote)
        self.assertEqual(checked.term.value, "8 months")
        self.assertEqual(checked.term_classification, "8_month_confirmed")


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


class FetchJobChecks(unittest.TestCase):
    def test_rejects_non_https_url_without_request(self):
        with (
            patch("requests.get") as mocked,
            self.assertRaisesRegex(ValueError, "https employer posting URL"),
        ):
            fetch_job("http://employer.example/jobs/123")
        mocked.assert_not_called()

    def test_extracts_html_and_removes_page_chrome(self):
        posting = fixture("job_explicit_eight_months.txt").replace("\n", "<br>")
        html = (
            "<html><head><style>.hidden{display:none}</style></head><body>"
            "<header>Header account link</header><nav>Navigation menu</nav>"
            f"<main>{posting}</main>"
            "<script>ignoreThisSecretInstruction()</script><footer>Footer links</footer>"
            "</body></html>"
        )
        response = html_response(html)
        with patch("requests.get", return_value=response) as mocked:
            text = fetch_job("https://employer.example/jobs/123")
        self.assertIn("Northstar Analytics", text)
        self.assertIn("8 months", text)
        self.assertNotIn("Navigation menu", text)
        self.assertNotIn("ignoreThisSecretInstruction", text)
        mocked.assert_called_once_with(
            "https://employer.example/jobs/123",
            headers={"User-Agent": "Mozilla/5.0 (compatible; personal-job-review/1.0)"},
            timeout=20,
        )

    def test_rejects_non_html_response(self):
        response = html_response("{}" * 200, content_type="application/json")
        with (
            patch("requests.get", return_value=response),
            self.assertRaisesRegex(ValueError, "did not return HTML"),
        ):
            fetch_job("https://employer.example/jobs/123")

    def test_rejects_redirect_to_non_https_url(self):
        response = html_response("A" * 400, url="http://internal.example/jobs/123")
        with (
            patch("requests.get", return_value=response),
            self.assertRaisesRegex(ValueError, "redirected to a non-https URL"),
        ):
            fetch_job("https://employer.example/jobs/123")

    def test_rejects_declared_oversized_page(self):
        response = html_response("A" * 400, content_length="2000001")
        with (
            patch("requests.get", return_value=response),
            self.assertRaisesRegex(ValueError, "Page too large"),
        ):
            fetch_job("https://employer.example/jobs/123")

    def test_rejects_actual_oversized_page(self):
        response = html_response("A" * 2_000_001)
        with (
            patch("requests.get", return_value=response),
            self.assertRaisesRegex(ValueError, "Page too large"),
        ):
            fetch_job("https://employer.example/jobs/123")

    def test_rejects_javascript_shell_with_too_little_text(self):
        response = html_response(
            "<html><body><div id='app'>Enable JavaScript</div><script>loadApp()</script></body></html>"
        )
        with (
            patch("requests.get", return_value=response),
            self.assertRaisesRegex(ValueError, "Posting text was not accessible"),
        ):
            fetch_job("https://employer.example/jobs/123")

    def test_network_timeout_is_not_hidden(self):
        with (
            patch("requests.get", side_effect=requests.Timeout("timed out")),
            self.assertRaises(requests.Timeout),
        ):
            fetch_job("https://employer.example/jobs/123")

    def test_http_error_is_not_hidden(self):
        response = html_response("A" * 400)
        response.raise_for_status.side_effect = requests.HTTPError("403 Forbidden")
        with (
            patch("requests.get", return_value=response),
            self.assertRaises(requests.HTTPError),
        ):
            fetch_job("https://employer.example/jobs/123")

    def test_limits_extracted_text_to_sixty_thousand_characters(self):
        response = html_response(f"<html><body>{'A' * 70_000}</body></html>")
        with patch("requests.get", return_value=response):
            text = fetch_job("https://employer.example/jobs/123")
        self.assertEqual(len(text), 60_000)


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
                    side_effect=lambda *_: make_analysis("", "variable_or_unclear"),
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
                    side_effect=lambda *_: make_analysis("", "variable_or_unclear"),
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
                patch("job_agent.make_analysis", return_value=make_analysis("")) as analyzed,
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
                patch("job_agent.make_analysis", return_value=make_analysis("")) as analyzed,
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
                patch("job_agent.make_analysis", return_value=make_analysis("")) as analyzed,
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


class RankingChecks(unittest.TestCase):
    def test_rank_uses_supported_terms_preferences_and_quoted_dates(self):
        a = make_analysis("Work term: 8 months.")
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
        a = make_analysis("", "variable_or_unclear")
        a.deadline = Fact(value="2026-10-10", source_quote="October 10, 2026 or October 20, 2026")
        a.publication_date = Fact(value="Not stated", source_quote="")
        self.assertIsNone(quoted_date(a.deadline))
        job = PreparedJob("abc", Path("packet.md"), "synthetic job", a)
        score, reasons = rank_job(job, CandidateProfile(), date(2026, 10, 3))
        self.assertEqual(score, 0)
        self.assertIn("employer publication date unknown (+0)", reasons)

    def test_past_deadline_is_not_called_closed(self):
        a = make_analysis("", "variable_or_unclear")
        a.deadline = Fact(value="2026-09-30", source_quote="Deadline: 2026-09-30")
        job = PreparedJob("abc", Path("packet.md"), "synthetic job", a)
        score, reasons = rank_job(job, CandidateProfile(), date(2026, 10, 3))
        self.assertEqual(score, -20)
        self.assertTrue(any("verify live status" in reason for reason in reasons))

    def test_queue_orders_new_jobs_by_score(self):
        strong = make_analysis("8 months")
        weak = make_analysis("", "variable_or_unclear")
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


class OutputChecks(unittest.TestCase):
    def test_packet_keeps_human_review_boundary_visible(self):
        resume = fixture("synthetic_resume.md")
        posting = fixture("job_explicit_eight_months.txt")
        quote = "Work term: January 4 to August 27, 2027 (8 months)."
        a = check_analysis(make_analysis(quote), resume, posting)
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
                patch("job_agent.make_analysis", return_value=make_analysis(quote)) as mocked,
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
                    return_value=make_analysis("", "variable_or_unclear"),
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
                patch("job_agent.make_analysis", return_value=make_analysis("")) as analyzed,
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


if __name__ == "__main__":
    unittest.main()
