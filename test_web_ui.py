import base64
import http.client
import json
import os
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from direction_suggestions import resume_fingerprint
from job_agent import read_tracker
from test_job_agent import fixture, make_analysis
from web_ui import LocalServer, packet_for_row, resume_from_request, review_path


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

    def test_review_reader_rejects_symbolic_link(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            reviews = root / "output" / "reviews"
            reviews.mkdir(parents=True)
            (reviews / ("a" * 12 + ".json")).symlink_to(root / "unrelated.json")
            with self.assertRaisesRegex(ValueError, "symbolic link"):
                review_path(root / "output", "a" * 12)


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

    def prepare_synthetic(self):
        term_quote = "Work term: January 4 to August 27, 2027 (8 months)."
        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "synthetic-test-key"}),
            patch("job_agent.make_analysis", return_value=make_analysis(term_quote)),
        ):
            status, _, raw = self.request("POST", "/api/prepare", self.prepare_payload())
        self.assertEqual(status, 200)
        return json.loads(raw)

    def test_local_page_and_empty_state_have_privacy_headers(self):
        status, headers, page = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"Co-op Prep", page)
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        status, headers, stylesheet = self.request("GET", "/review.css")
        self.assertEqual(status, 200)
        self.assertIn(b"review-editor", stylesheet)
        self.assertIn("text/css", headers["Content-Type"])
        status, _, stylesheet = self.request("GET", "/direction.css")
        self.assertEqual(status, 200)
        self.assertIn(b"direction-panel", stylesheet)
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

    def test_directions_work_without_key_and_confirmed_roles_reach_analysis(self):
        payload = self.prepare_payload()
        payload["profile_json"] = (Path(__file__).parent / "profile.example.json").read_text()
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            status, _, raw = self.request("POST", "/api/directions", payload)
        self.assertEqual(status, 200)
        result = json.loads(raw)
        self.assertEqual(result["resume_fingerprint"], resume_fingerprint(payload["resume_text"]))
        self.assertIn("Data Analyst Co-op", [item["role"] for item in result["suggestions"]])
        self.assertEqual(result["current_roles"], ["Data Analyst Co-op", "Business Intelligence Co-op"])
        self.assertEqual(read_tracker(self.out / "applications.csv"), [])

        payload["confirmed_roles"] = ["Data Operations Co-op"]
        payload["direction_fingerprint"] = result["resume_fingerprint"]
        term_quote = "Work term: January 4 to August 27, 2027 (8 months)."
        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "synthetic-test-key"}),
            patch("job_agent.make_analysis", return_value=make_analysis(term_quote)) as analyzed,
        ):
            status, _, _ = self.request("POST", "/api/prepare", payload)
        self.assertEqual(status, 200)
        used_profile = analyzed.call_args.args[3]
        self.assertEqual(used_profile.preferences.target_roles, ["Data Operations Co-op"])
        self.assertEqual(used_profile.preferences.preferred_locations[0], "Toronto, Ontario")

    def test_stale_direction_confirmation_is_rejected_before_model(self):
        payload = self.prepare_payload()
        payload["confirmed_roles"] = ["Data Analyst Co-op"]
        payload["direction_fingerprint"] = "0" * 64
        with patch("job_agent.make_analysis") as analyzed:
            status, _, raw = self.request("POST", "/api/prepare", payload)
        self.assertEqual(status, 400)
        self.assertIn(b"Resume changed", raw)
        analyzed.assert_not_called()

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

    def test_review_is_local_editable_and_does_not_change_generated_packet(self):
        prepared = self.prepare_synthetic()
        job_id = prepared["job"]["job_id"]
        original_packet = prepared["packet"]
        self.assertFalse(prepared["review"]["saved"])
        self.assertIsNone(prepared["review"]["draft"])
        payload = {
            "job_id": job_id,
            "draft": "I reviewed this synthetic application paragraph.",
            "notes": "Confirm the live employer deadline before applying.",
            "checks": {
                "posting_status": False,
                "term_and_dates": True,
                "resume_and_draft": True,
            },
            "base_revision": "",
        }
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            status, _, raw = self.request("POST", "/api/review", payload)
        self.assertEqual(status, 200)
        saved = json.loads(raw)["review"]
        self.assertTrue(saved["saved"])
        self.assertEqual(saved["draft"], payload["draft"])
        self.assertEqual(saved["checks"]["posting_status"], False)
        self.assertEqual(len(saved["revision"]), 64)
        self.assertEqual(review_path(self.out, job_id).stat().st_mode & 0o777, 0o600)

        status, _, raw = self.request("GET", f"/api/packet?id={job_id}")
        self.assertEqual(status, 200)
        reopened = json.loads(raw)
        self.assertEqual(reopened["review"]["draft"], payload["draft"])
        self.assertEqual(reopened["packet"], original_packet)

        payload["draft"] = "A newer version."
        status, _, raw = self.request("POST", "/api/review", payload)
        self.assertEqual(status, 409)
        self.assertIn(b"another tab", raw)
        payload["base_revision"] = saved["revision"]
        status, _, raw = self.request("POST", "/api/review", payload)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)["review"]["draft"], "A newer version.")

    def test_review_rejects_untracked_job_and_invalid_checks(self):
        unknown = "a" * 12
        payload = {
            "job_id": unknown, "draft": "test", "notes": "",
            "checks": {"posting_status": False, "term_and_dates": False,
                       "resume_and_draft": False},
            "base_revision": "",
        }
        status, _, _ = self.request("POST", "/api/review", payload)
        self.assertEqual(status, 400)
        self.assertFalse(review_path(self.out, unknown).exists())

        prepared = self.prepare_synthetic()
        payload["job_id"] = prepared["job"]["job_id"]
        payload["checks"]["posting_status"] = "yes"
        status, _, raw = self.request("POST", "/api/review", payload)
        self.assertEqual(status, 400)
        self.assertIn(b"three true/false values", raw)
        self.assertFalse(review_path(self.out, payload["job_id"]).exists())


    def saved_export_review(self, job_id, **overrides):
        payload = {
            "job_id": job_id, "draft": "My reviewed application paragraph.",
            "notes": "PRIVATE: follow up with my adviser.",
            "checks": {"posting_status": True, "term_and_dates": True,
                       "resume_and_draft": True}, "base_revision": "",
        }
        payload.update(overrides)
        status, _, raw = self.request("POST", "/api/review", payload)
        self.assertEqual(status, 200)
        return json.loads(raw)["review"]

    def test_application_export_contains_only_saved_draft_and_does_not_mutate(self):
        job_id = self.prepare_synthetic()["job"]["job_id"]
        saved = self.saved_export_review(job_id)
        before = {path: path.read_bytes() for path in self.out.rglob("*") if path.is_file()}
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}), patch("job_agent.make_analysis") as analyzed:
            status, headers, raw = self.request("POST", "/api/export", {
                "job_id": job_id, "base_revision": saved["revision"],
            })
        self.assertEqual(status, 200)
        self.assertEqual(headers["Cache-Control"], "no-store")
        result = json.loads(raw)
        self.assertEqual(result["text"], saved["draft"] + "\n")
        self.assertEqual(result["filename"], f"{job_id}-application.txt")
        self.assertNotIn("PRIVATE", raw.decode())
        after = {path: path.read_bytes() for path in self.out.rglob("*") if path.is_file()}
        self.assertEqual(before, after)
        analyzed.assert_not_called()

    def test_export_requires_saved_nonempty_draft_and_all_manual_checks(self):
        job_id = self.prepare_synthetic()["job"]["job_id"]
        status, _, _ = self.request("POST", "/api/export", {"job_id": "a" * 12})
        self.assertEqual(status, 400)
        status, _, raw = self.request("POST", "/api/export", {"job_id": job_id})
        self.assertEqual(status, 400)
        self.assertIn(b"Save your manual review", raw)
        saved = self.saved_export_review(job_id, checks={
            "posting_status": False, "term_and_dates": True, "resume_and_draft": True,
        })
        status, _, raw = self.request("POST", "/api/export", {
            "job_id": job_id, "base_revision": saved["revision"],
        })
        self.assertEqual(status, 400)
        self.assertIn(b"all three manual checks", raw)
        saved = self.saved_export_review(job_id, draft=" \n ", base_revision=saved["revision"])
        status, _, raw = self.request("POST", "/api/export", {
            "job_id": job_id, "base_revision": saved["revision"],
        })
        self.assertEqual(status, 400)
        self.assertIn(b"Write an application paragraph", raw)

    def test_export_rejects_stale_revision_and_cross_origin(self):
        job_id = self.prepare_synthetic()["job"]["job_id"]
        saved = self.saved_export_review(job_id)
        self.saved_export_review(job_id, draft="Newer paragraph.", base_revision=saved["revision"])
        payload = {"job_id": job_id, "base_revision": saved["revision"]}
        status, _, raw = self.request("POST", "/api/export", payload)
        self.assertEqual(status, 409)
        self.assertIn(b"Reopen the job", raw)
        status, _, _ = self.request("POST", "/api/export", payload, {"Origin": "https://attacker.example"})
        self.assertEqual(status, 403)


if __name__ == "__main__":
    unittest.main()
