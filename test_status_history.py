import csv
import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from job_agent import StatusConflict, read_tracker, record_status, status_history, status_revision, write_tracker


def legacy_row(job_id="a" * 12, status="prepared", outcome_at=""):
    return {"job_id": job_id, "employer": "Example", "title": "Synthetic role",
            "url": "", "packet": "synthetic.md", "prepared_at": "2026-10-01T10:00:00-04:00",
            "status": status, "outcome_at": outcome_at, "content_fingerprint": ""}


class StatusHistoryChecks(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.tracker = Path(self.temporary.name) / "applications.csv"
        write_tracker(self.tracker, [legacy_row()])

    def tearDown(self):
        self.temporary.cleanup()

    def test_transitions_preserve_prefix_and_same_status_is_noop(self):
        with patch("job_agent.now_toronto", side_effect=["2026-10-02T10:00:00-04:00", "2026-10-03T10:00:00-04:00"]):
            applied = record_status(self.tracker, "a" * 12, "applied", "cli")
            prefix = status_history(applied)
            interviewed = record_status(self.tracker, "a" * 12, "interview", "web", status_revision(applied))
        events = status_history(interviewed)
        self.assertEqual(events[:-1], prefix)
        self.assertEqual([event["to"] for event in events], ["prepared", "applied", "interview"])
        self.assertEqual(events[-1]["source"], "web")
        before = self.tracker.read_bytes()
        record_status(self.tracker, "a" * 12, "interview", "web", status_revision(interviewed))
        self.assertEqual(self.tracker.read_bytes(), before)
        self.assertEqual(self.tracker.stat().st_mode & 0o777, 0o600)

    def test_legacy_csv_remains_readable_without_inventing_earlier_events(self):
        row = legacy_row(status="interview")
        with self.tracker.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(row))
            writer.writeheader()
            writer.writerow(row)
        events = status_history(read_tracker(self.tracker)[0])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["to"], "interview")
        self.assertEqual(events[0]["at"], "")
        self.assertEqual(events[0]["source"], "legacy")
        result = record_status(self.tracker, "a" * 12, "offer", "cli")
        self.assertEqual(status_history(result)[:-1], events)

    def test_stale_revision_and_bad_status_do_not_overwrite(self):
        old = status_revision(read_tracker(self.tracker)[0])
        record_status(self.tracker, "a" * 12, "applied", "cli")
        before = self.tracker.read_bytes()
        with self.assertRaises(StatusConflict):
            record_status(self.tracker, "a" * 12, "interview", "web", old)
        with self.assertRaises(ValueError):
            record_status(self.tracker, "a" * 12, "invented", "web")
        with self.assertRaises(ValueError):
            record_status(self.tracker, "b" * 12, "offer", "cli")
        self.assertEqual(self.tracker.read_bytes(), before)

    def test_corrupt_history_is_preserved_for_recovery(self):
        for malformed in ["not json", "[]", json.dumps([{"to": "applied"}])]:
            row = legacy_row()
            row["status_history"] = malformed
            write_tracker(self.tracker, [row])
            before = self.tracker.read_bytes()
            with self.assertRaisesRegex(ValueError, "history is invalid"):
                record_status(self.tracker, "a" * 12, "applied", "cli")
            self.assertEqual(self.tracker.read_bytes(), before)

    def test_failed_atomic_write_keeps_original_tracker(self):
        before = self.tracker.read_bytes()
        with patch("job_agent.os.replace", side_effect=OSError("synthetic disk failure")):
            with self.assertRaises(OSError):
                record_status(self.tracker, "a" * 12, "applied", "cli")
        self.assertEqual(self.tracker.read_bytes(), before)
        self.assertEqual(list(self.tracker.parent.glob(".applications-*.tmp")), [])

    def test_parallel_updates_preserve_both_jobs(self):
        write_tracker(self.tracker, [legacy_row(), legacy_row("b" * 12)])
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(record_status, self.tracker, job_id, "applied", "cli")
                       for job_id in ("a" * 12, "b" * 12)]
            for future in futures:
                future.result(timeout=5)
        rows = read_tracker(self.tracker)
        self.assertEqual([row["status"] for row in rows], ["applied", "applied"])
        self.assertTrue(all(len(status_history(row)) == 2 for row in rows))


if __name__ == "__main__":
    unittest.main()
