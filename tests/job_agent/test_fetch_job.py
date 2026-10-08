"""网页读取的模拟测试：不连接真实雇主网站。"""

import unittest
from unittest.mock import patch

import requests

from job_agent import fetch_job
from tests.job_agent.support import fixture, html_response


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
