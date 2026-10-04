import base64
import http.client
import json
import os
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from job_agent import read_tracker
from test_job_agent import fixture, make_analysis
from web_ui import LocalServer, packet_for_row, resume_from_request


class WebInputChecks(unittest.TestCase):
    def test_text_resume_upload_stays_in_memory(self):
        resume = fixture("synthetic_resume.md")
        result = resume_from_request({
            "resume_file": {
                "name": "synthetic_resume.md",
                "data": base64.b64encode(resume.encode()).decode(),
            }
        })
        self.assertEqual(result, resume)

    def test_invalid_pdf_is_a_clear_input_error(self):
        with self.assertRaisesRegex(ValueError, "could not be extracted"):
            resume_from_request({
                "resume_file": {
                    "name": "bad.pdf",
                    "data": base64.b64encode(b"not a PDF").decode(),
                }
            })

    def test_packet_reader_rejects_outside_path(self):
        with TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "outside"):
                packet_for_row({"packet": "../private.md"}, Path(directory) / "output")


class LocalHTTPChecks(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.out = Path(self.temporary.name) / "output"
        self.server = LocalServer(0, self.out)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temporary.cleanup()

    def request(self, method, path, data=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        body = json.dumps(data).encode() if data is not None else None
        request_headers = dict(headers or {})
        if body is not None:
            request_headers.setdefault("Content-Type", "application/json")
            request_headers.setdefault("X-Job-Agent", "local-ui")
        connection.request(method, path, body=body, headers=request_headers)
        response = connection.getresponse()
        raw = response.read()
        result = (response.status, dict(response.getheaders()), raw)
        connection.close()
        return result

    def prepare_payload(self):
        return {
            "resume_text": fixture("synthetic_resume.md"),
            "profile_json": "",
            "source_type": "text",
            "posting_text": fixture("job_explicit_eight_months.txt"),
        }

    def test_local_page_and_empty_state_have_privacy_headers(self):
        status, headers, page = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"Co-op Prep", page)
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            status, _, raw = self.request("GET", "/api/state")
        self.assertEqual(status, 200)
        state = json.loads(raw)
        self.assertFalse(state["api_key_ready"])
        self.assertEqual(state["jobs"], [])

    def test_cross_origin_and_missing_custom_header_are_rejected(self):
        payload = self.prepare_payload()
        status, _, _ = self.request("POST", "/api/prepare", payload, {
            "Origin": "https://attacker.example",
        })
        self.assertEqual(status, 403)
        status, _, _ = self.request("POST", "/api/prepare", payload, {
            "X-Job-Agent": "wrong",
        })
        self.assertEqual(status, 403)

    def test_missing_key_blocks_new_job_before_fetch(self):
        payload = self.prepare_payload()
        payload["source_type"] = "url"
        payload["url"] = "https://employer.example/jobs/123"
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}), patch("web_ui.fetch_job") as fetched:
            status, _, raw = self.request("POST", "/api/prepare", payload)
        self.assertEqual(status, 400)
        self.assertIn(b"OPENAI_API_KEY", raw)
        fetched.assert_not_called()

    def test_prepare_duplicate_packet_and_manual_status_update(self):
        payload = self.prepare_payload()
        term_quote = "Work term: January 4 to August 27, 2027 (8 months)."
        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "synthetic-test-key"}),
            patch("job_agent.make_analysis", return_value=make_analysis(term_quote)) as analyzed,
        ):
            status, _, raw = self.request("POST", "/api/prepare", payload)
            self.assertEqual(status, 200)
            result = json.loads(raw)
            self.assertFalse(result["duplicate"])
            self.assertIn("Prepared only; application not submitted", result["packet"])
            job_id = result["job"]["job_id"]
            status, _, raw = self.request("POST", "/api/prepare", payload)
            self.assertEqual(status, 200)
            self.assertTrue(json.loads(raw)["duplicate"])
        analyzed.assert_called_once()

        status, _, raw = self.request("GET", f"/api/packet?id={job_id}")
        self.assertEqual(status, 200)
        self.assertIn("Data Analyst Co-op", json.loads(raw)["packet"])
        status, _, raw = self.request("POST", "/api/feedback", {
            "job_id": job_id, "status": "applied",
        })
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)["job"]["status"], "applied")
        rows = read_tracker(self.out / "applications.csv")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "applied")


if __name__ == "__main__":
    unittest.main()
