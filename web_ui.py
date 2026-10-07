#!/usr/bin/env python3
"""Local-only browser review UI for the job preparation workflow."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
import re
import tempfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from direction_suggestions import (
    ROLE_FAMILIES, apply_confirmed_directions, get_role_family, resume_fingerprint, suggest_directions,
)
from resume_evidence import extract_resume_evidence, review_resume_evidence
from direction_report import build_direction_report
from job_agent import (
    CandidateProfile,
    STATUSES,
    StatusConflict,
    already_tracked,
    fetch_job,
    job_id_for_source,
    now_toronto,
    posting_fingerprint,
    prepare_job,
    read_resume_bytes,
    read_tracker,
    record_status,
    status_history,
    status_revision,
    validate_profile,
)


WEB_DIR = Path(__file__).parent / "web"
MAX_REQUEST_BYTES = 4_000_000
MAX_RESUME_BYTES = 2_500_000
MAX_RESUME_CHARS = 80_000
MAX_POSTING_CHARS = 60_000
JOB_ID_PATTERN = re.compile(r"[0-9a-f]{12}\Z")
REVISION_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
REVIEW_CHECKS = ("posting_status", "term_and_dates", "resume_and_draft")


class ReviewConflict(Exception):
    """The browser is trying to overwrite a newer local review."""


def resume_from_request(data: dict) -> str:
    pasted = data.get("resume_text", "")
    if not isinstance(pasted, str):
        raise ValueError("Resume text must be a string.")
    if pasted.strip():
        resume = pasted
    else:
        uploaded = data.get("resume_file")
        if not isinstance(uploaded, dict):
            raise ValueError("Paste a resume or select a text-based PDF, .txt, or .md file.")
        name, encoded = uploaded.get("name"), uploaded.get("data")
        if not isinstance(name, str) or not isinstance(encoded, str) or len(name) > 200:
            raise ValueError("Invalid resume upload.")
        try:
            raw = base64.b64decode(encoded, validate=True)
        except binascii.Error as exc:
            raise ValueError("Resume upload could not be decoded.") from exc
        if len(raw) > MAX_RESUME_BYTES:
            raise ValueError("Resume upload exceeds the 2.5 MB limit.")
        try:
            resume = read_resume_bytes(raw, Path(name).suffix)
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("Resume file could not be extracted; use a text-based PDF or text file.") from exc
    if len(resume.strip()) < 150:
        raise ValueError("Resume text is too short or could not be extracted.")
    if len(resume) > MAX_RESUME_CHARS:
        raise ValueError("Resume text exceeds the 80,000-character limit.")
    return resume


def profile_from_request(data: dict, resume: str) -> CandidateProfile:
    raw = data.get("profile_json", "")
    if not isinstance(raw, str) or len(raw) > 30_000:
        raise ValueError("Profile JSON is invalid or too large.")
    if not raw.strip():
        return CandidateProfile()
    try:
        return validate_profile(json.loads(raw), resume)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Profile JSON could not be parsed: {exc.msg}") from exc


def public_row(row: dict[str, str]) -> dict:
    result = {key: row.get(key, "") for key in (
        "job_id", "employer", "title", "url", "prepared_at", "status", "outcome_at"
    )}
    result.update(status_history=status_history(row), status_revision=status_revision(row))
    return result


def tracked_row(rows: list[dict[str, str]], job_id: str, url: str | None, posting: str = "") -> dict[str, str] | None:
    fingerprint = posting_fingerprint(posting) if posting else None
    return next(
        (row for row in rows if already_tracked([row], job_id, url, fingerprint)), None
    )


def packet_for_row(row: dict[str, str], out: Path) -> str:
    packet = Path(row.get("packet", ""))
    if not packet.is_absolute():
        packet = Path.cwd() / packet
    packet = packet.resolve()
    try:
        packet.relative_to(out.resolve())
    except ValueError as exc:
        raise ValueError("Packet path is outside the selected output directory.") from exc
    if packet.suffix != ".md" or not packet.is_file():
        raise ValueError("Packet file is missing or invalid.")
    return packet.read_text(encoding="utf-8")


def review_path(out: Path, job_id: str) -> Path:
    if not JOB_ID_PATTERN.fullmatch(job_id):
        raise ValueError("Invalid job ID.")
    directory = out / "reviews"
    path = directory / f"{job_id}.json"
    if directory.is_symlink() or path.is_symlink():
        raise ValueError("Review path cannot be a symbolic link.")
    return path


def empty_review() -> dict:
    return {
        "saved": False, "draft": None, "notes": "",
        "checks": {name: False for name in REVIEW_CHECKS},
        "saved_at": "", "revision": "",
    }


def validate_review_fields(data: dict) -> tuple[str, str, dict[str, bool]]:
    draft, notes, checks = data.get("draft"), data.get("notes"), data.get("checks")
    if not isinstance(draft, str) or len(draft) > 5_000:
        raise ValueError("Edited application paragraph must be at most 5,000 characters.")
    if not isinstance(notes, str) or len(notes) > 10_000:
        raise ValueError("Review notes must be at most 10,000 characters.")
    if not isinstance(checks, dict) or set(checks) != set(REVIEW_CHECKS) or any(
        type(checks[name]) is not bool for name in REVIEW_CHECKS
    ):
        raise ValueError("Review checklist must contain three true/false values.")
    return draft, notes, checks


def load_review(out: Path, job_id: str) -> dict:
    path = review_path(out, job_id)
    if not path.exists():
        return empty_review()
    if path.stat().st_size > 100_000:
        raise ValueError("Saved review is too large; it was not overwritten.")
    raw = path.read_bytes()
    stored = json.loads(raw)
    if not isinstance(stored, dict):
        raise ValueError("Saved review is invalid; it was not overwritten.")
    draft, notes, checks = validate_review_fields(stored)
    saved_at = stored.get("saved_at")
    if not isinstance(saved_at, str):
        raise ValueError("Saved review is invalid; it was not overwritten.")
    return {
        "saved": True, "draft": draft, "notes": notes, "checks": checks,
        "saved_at": saved_at, "revision": hashlib.sha256(raw).hexdigest(),
    }


def save_review(out: Path, job_id: str, data: dict) -> dict:
    draft, notes, checks = validate_review_fields(data)
    base_revision = data.get("base_revision")
    if not isinstance(base_revision, str) or (
        base_revision and not REVISION_PATTERN.fullmatch(base_revision)
    ):
        raise ValueError("Invalid review revision.")
    current = load_review(out, job_id)
    if current["revision"] != base_revision:
        raise ReviewConflict("This review changed in another tab. Reopen the job before saving.")
    path = review_path(out, job_id)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    payload = {
        "draft": draft, "notes": notes, "checks": checks,
        "saved_at": now_toronto(),
    }
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    descriptor, temporary = tempfile.mkstemp(prefix=f".{job_id}-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return load_review(out, job_id)


class LocalServer(HTTPServer):
    def __init__(self, port: int, out: Path):
        self.out = out.resolve()
        super().__init__(("127.0.0.1", port), LocalHandler)


class LocalHandler(BaseHTTPRequestHandler):
    server: LocalServer

    def log_message(self, _format: str, *_args: object) -> None:
        # Request bodies and private filenames should not enter terminal logs.
        pass

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'",
        )
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload: dict) -> None:
        self._send(status, "application/json; charset=utf-8", json.dumps(payload).encode("utf-8"))

    def _same_origin(self) -> bool:
        expected = f"127.0.0.1:{self.server.server_port}"
        origin = self.headers.get("Origin")
        return self.headers.get("Host") == expected and (
            origin is None or origin == f"http://{expected}"
        )

    def do_GET(self) -> None:
        if not self._same_origin():
            self._json(403, {"error": "Local origin required."})
            return
        parsed = urlsplit(self.path)
        if parsed.path in {"/", "/app.css", "/packet.css", "/review.css", "/direction.css", "/evidence.css", "/app.js"}:
            filename = {"/": "index.html", "/app.css": "app.css",
                        "/packet.css": "packet.css", "/review.css": "review.css",
                        "/direction.css": "direction.css",
                        "/evidence.css": "evidence.css",
                        "/app.js": "app.js"}[parsed.path]
            mime = "text/html" if filename.endswith(".html") else (
                "text/css" if filename.endswith(".css") else "application/javascript"
            )
            self._send(200, f"{mime}; charset=utf-8", (WEB_DIR / filename).read_bytes())
            return
        if parsed.path == "/api/state":
            rows = read_tracker(self.server.out / "applications.csv")
            queue = self.server.out / "priority_queue.md"
            try:
                self._json(200, {
                    "jobs": [public_row(row) for row in reversed(rows)],
                    "queue": queue.read_text(encoding="utf-8") if queue.is_file() else "",
                    "api_key_ready": bool(os.getenv("OPENAI_API_KEY")),
                    "role_families": ROLE_FAMILIES,
                })
            except (OSError, ValueError) as exc:
                self._json(400, {"error": str(exc)})
            return
        if parsed.path == "/api/packet":
            job_id = parse_qs(parsed.query).get("id", [""])[0]
            if not JOB_ID_PATTERN.fullmatch(job_id):
                self._json(400, {"error": "Invalid job ID."})
                return
            row = next((r for r in read_tracker(self.server.out / "applications.csv")
                        if r.get("job_id") == job_id), None)
            if row is None:
                self._json(404, {"error": "Job not found."})
                return
            try:
                self._json(200, {
                    "job": public_row(row), "packet": packet_for_row(row, self.server.out),
                    "review": load_review(self.server.out, job_id),
                })
            except (OSError, ValueError) as exc:
                self._json(400, {"error": str(exc)})
            return
        self._json(404, {"error": "Not found."})

    def do_POST(self) -> None:
        if not self._same_origin() or self.headers.get("X-Job-Agent") != "local-ui":
            self._json(403, {"error": "Local UI request required."})
            return
        if self.headers.get("Content-Type", "").partition(";")[0].strip() != "application/json":
            self._json(415, {"error": "JSON request required."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_REQUEST_BYTES:
                raise ValueError("Request is empty or exceeds the 4 MB limit.")
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(data, dict):
                raise ValueError("Request must be a JSON object.")
            if self.path == "/api/prepare":
                self._prepare(data)
            elif self.path == "/api/directions":
                self._directions(data)
            elif self.path == "/api/resume-evidence":
                self._json(200, extract_resume_evidence(resume_from_request(data)))
            elif self.path == "/api/resume-evidence/review":
                self._json(200, review_resume_evidence(resume_from_request(data), data))
            elif self.path == "/api/direction-report":
                resume = resume_from_request(data)
                report = build_direction_report(resume, data)
                report["current_roles"] = profile_from_request(data, resume).preferences.target_roles
                self._json(200, report)
            elif self.path == "/api/feedback":
                self._feedback(data)
            elif self.path == "/api/review":
                self._review(data)
            elif self.path == "/api/export":
                self._export(data)
            else:
                self._json(404, {"error": "Not found."})
        except (ReviewConflict, StatusConflict) as exc:
            self._json(409, {"error": str(exc)})
        except (ValueError, UnicodeError, OSError) as exc:
            self._json(400, {"error": str(exc)})
        except Exception as exc:
            # Model/network failures should reach the browser as an error, not a dropped connection.
            message = str(exc).replace(os.getenv("OPENAI_API_KEY") or "\0", "[redacted]")
            self._json(502, {"error": f"Preparation failed: {message[:500]}"})

    def _prepare(self, data: dict) -> None:
        resume = resume_from_request(data)
        profile = apply_confirmed_directions(
            profile_from_request(data, resume), data, resume
        )
        source_type = data.get("source_type")
        rows = read_tracker(self.server.out / "applications.csv")
        if source_type == "url":
            url = data.get("url")
            if not isinstance(url, str) or not 0 < len(url) <= 2048:
                raise ValueError("Enter one HTTPS job URL.")
            url = url.strip()
            parts = urlsplit(url)
            if parts.scheme != "https" or not parts.netloc:
                raise ValueError("Use an HTTPS employer posting URL.")
            existing = tracked_row(rows, job_id_for_source(url), url)
            if existing:
                self._json(200, {"duplicate": True, "job": public_row(existing),
                                 "packet": packet_for_row(existing, self.server.out),
                                 "review": load_review(self.server.out, existing["job_id"])})
                return
            if not os.getenv("OPENAI_API_KEY"):
                raise ValueError("Set OPENAI_API_KEY in the server terminal before preparing a new job.")
            posting, source = fetch_job(url), url
        elif source_type == "text":
            posting = data.get("posting_text")
            if not isinstance(posting, str) or len(posting.strip()) < 300:
                raise ValueError("Paste at least 300 characters of the employer posting.")
            if len(posting) > MAX_POSTING_CHARS:
                raise ValueError("Posting exceeds the 60,000-character limit.")
            url, source = None, "Pasted posting"
            existing = tracked_row(rows, job_id_for_source(None, posting), None, posting)
            if existing:
                self._json(200, {"duplicate": True, "job": public_row(existing),
                                 "packet": packet_for_row(existing, self.server.out),
                                 "review": load_review(self.server.out, existing["job_id"])})
                return
            if not os.getenv("OPENAI_API_KEY"):
                raise ValueError("Set OPENAI_API_KEY in the server terminal before preparing a new job.")
        else:
            raise ValueError("Choose a job URL or pasted posting text.")

        job = prepare_job(resume, profile, posting, source, url, self.server.out)
        if job is None:
            existing = tracked_row(
                read_tracker(self.server.out / "applications.csv"),
                job_id_for_source(url, posting), url, posting,
            )
            if existing is None:
                raise ValueError("The job was skipped but its tracker row was not found.")
            self._json(200, {"duplicate": True, "job": public_row(existing),
                             "packet": packet_for_row(existing, self.server.out),
                             "review": load_review(self.server.out, existing["job_id"])})
            return
        row = tracked_row(read_tracker(self.server.out / "applications.csv"), job.job_id, url)
        if row is None:
            raise ValueError("Prepared job was not found in the tracker.")
        self._json(200, {"duplicate": False, "job": public_row(row),
                         "packet": packet_for_row(row, self.server.out),
                         "review": load_review(self.server.out, job.job_id)})

    def _directions(self, data: dict) -> None:
        family = get_role_family(data.get("role_family", ""))
        resume = resume_from_request(data)
        profile = profile_from_request(data, resume)
        self._json(200, {
            "suggestions": suggest_directions(resume),
            "role_family": family,
            "current_roles": profile.preferences.target_roles,
            "resume_fingerprint": resume_fingerprint(resume),
        })

    def _review(self, data: dict) -> None:
        job_id = data.get("job_id")
        if not isinstance(job_id, str) or not JOB_ID_PATTERN.fullmatch(job_id):
            raise ValueError("Invalid job ID.")
        row = next((item for item in read_tracker(self.server.out / "applications.csv")
                    if item.get("job_id") == job_id), None)
        if row is None:
            raise ValueError("Job ID not found in tracker.")
        # Refuse to edit a review when its source packet is no longer available.
        packet_for_row(row, self.server.out)
        self._json(200, {"review": save_review(self.server.out, job_id, data)})

    def _export(self, data: dict) -> None:
        job_id = data.get("job_id")
        if not isinstance(job_id, str) or not JOB_ID_PATTERN.fullmatch(job_id):
            raise ValueError("Invalid job ID.")
        row = next((item for item in read_tracker(self.server.out / "applications.csv")
                    if item.get("job_id") == job_id), None)
        if row is None:
            raise ValueError("Job ID not found in tracker.")
        packet_for_row(row, self.server.out)
        review = load_review(self.server.out, job_id)
        if not review["saved"]:
            raise ValueError("Save your manual review before exporting the application paragraph.")
        if data.get("base_revision") != review["revision"]:
            raise ReviewConflict("This review changed in another tab. Reopen the job before exporting.")
        if not all(review["checks"].values()):
            raise ValueError("Complete all three manual checks and save before exporting.")
        if not review["draft"].strip():
            raise ValueError("Write an application paragraph and save before exporting.")
        self._json(200, {
            "filename": f"{job_id}-application.txt",
            "text": review["draft"].strip() + "\n",
        })

    def _feedback(self, data: dict) -> None:
        job_id, status = data.get("job_id"), data.get("status")
        if not isinstance(job_id, str) or not JOB_ID_PATTERN.fullmatch(job_id):
            raise ValueError("Invalid job ID.")
        if status not in STATUSES:
            raise ValueError("Invalid application status.")
        base_revision = data.get("base_revision")
        if base_revision is not None and (
            not isinstance(base_revision, str) or not REVISION_PATTERN.fullmatch(base_revision)
        ):
            raise ValueError("Invalid status revision.")
        row = record_status(self.server.out / "applications.csv", job_id, status, "web", base_revision)
        self._json(200, {"job": public_row(row)})


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local browser review interface.")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--out", type=Path, default=Path("job_agent_output"))
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error("Port must be between 0 and 65535.")
    server = LocalServer(args.port, args.out)
    print(f"Local UI: http://127.0.0.1:{server.server_port}/")
    print(f"Output directory: {server.out}")
    print("Press Ctrl+C to stop. Do not expose this server through a public tunnel.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
