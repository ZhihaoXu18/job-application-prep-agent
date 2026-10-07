import copy
import unittest

from direction_suggestions import suggest_directions
from resume_evidence import extract_resume_evidence, review_resume_evidence
from test_job_agent import fixture


def review_payload(draft):
    return {"evidence_fingerprint": draft["resume_fingerprint"], "evidence_edits": [
        {key: row[key] for key in ("id", "kind", "labels", "included", "note")}
        for row in draft["evidence"]
    ]}


class ResumeEvidenceChecks(unittest.TestCase):
    def test_synthetic_quotes_have_exact_offsets_and_stable_ids(self):
        resume = fixture("synthetic_resume.md")
        draft = extract_resume_evidence(resume)
        self.assertEqual(draft, extract_resume_evidence(resume))
        self.assertFalse(draft["reviewed"])
        for row in draft["evidence"]:
            self.assertEqual(resume[row["start"]:row["end"]], row["quote"])
            self.assertIn(row["quote"], resume.splitlines()[row["line"] - 1])
        self.assertEqual(len({row["id"] for row in draft["evidence"]}), len(draft["evidence"]))

    def test_contexts_remain_distinct_in_both_languages(self):
        resume = "\n".join([
            "Built SQL reports in a student project.", "Coursework: Python and Statistics.",
            "Currently learning React.", "No experience with Tableau.", "Skills: Excel.",
            "使用 Python 清洗数据。", "课程：财务报表与会计。", "正在学习 SQL。", "不会 Python。",
        ])
        self.assertEqual([row["kind"] for row in extract_resume_evidence(resume)["evidence"]],
                         ["practice", "course", "learning", "negated", "mentioned",
                          "practice", "course", "learning", "negated"])

    def test_course_section_does_not_become_practical_experience(self):
        rows = extract_resume_evidence("## Education\nBuilt SQL reports in a course.\nPython\n## Projects\nUsed Python.")["evidence"]
        self.assertEqual([row["kind"] for row in rows], ["course", "course", "practice"])

    def test_comma_lists_keep_negation_or_learning_and_contrasts_separate(self):
        rows = extract_resume_evidence("No experience with SQL, Python, Excel, but built Tableau dashboards.\nLearning SQL, Python.")["evidence"]
        self.assertEqual([row["kind"] for row in rows], ["negated", "negated", "negated", "practice", "learning", "learning"])
        suggestions = suggest_directions("No experience with SQL, Python, Excel, but built Tableau dashboards.")
        self.assertEqual([item["role"] for item in suggestions], ["Business Intelligence Co-op"])

    def test_negation_does_not_generate_positive_directions(self):
        for resume in ("No experience with SQL or Python.", "I haven't used SQL or Python.",
                       "不会 SQL，也不会 Python。", "Not proficient in SQL and Python."):
            with self.subTest(resume=resume):
                self.assertEqual(suggest_directions(resume), [])
        self.assertTrue(suggest_directions("Not only SQL but also Python."))

    def test_exact_quotes_keep_numbers_and_crlf(self):
        resume = "## Projects\r\n  - Cleaned 25,000 rows with Python; built SQL reports.\r\n"
        rows = extract_resume_evidence(resume)["evidence"]
        self.assertIn("25,000", rows[0]["quote"])
        for row in rows:
            self.assertEqual(resume[row["start"]:row["end"]], row["quote"])

    def test_unknown_skills_remain_absent_not_assumed_missing(self):
        draft = extract_resume_evidence("Community outreach volunteer and event coordinator.")
        self.assertEqual(draft["evidence"], [])
        self.assertNotIn("gaps", draft)

    def test_output_limits_do_not_truncate_evidence_into_false_quotes(self):
        draft = extract_resume_evidence("\n".join(f"Used Python for project {i}." for i in range(45)))
        self.assertEqual(len(draft["evidence"]), 40)
        self.assertEqual(draft["omitted_fragments"], 5)
        long_draft = extract_resume_evidence("Used Python " + "x" * 2100)
        self.assertEqual(long_draft["evidence"], [])
        self.assertEqual(long_draft["omitted_fragments"], 1)

    def test_review_annotations_are_bounded_and_do_not_modify_source_draft(self):
        resume = "Used SQL and Python."
        draft = extract_resume_evidence(resume)
        payload = review_payload(draft)
        payload["evidence_edits"][0].update(kind="course", labels=["SQL"], included=False, note="Synthetic review note")
        result = review_resume_evidence(resume, payload)
        self.assertTrue(result["reviewed"])
        self.assertEqual(result["evidence"][0]["kind"], "course")
        self.assertFalse(result["evidence"][0]["included"])
        self.assertEqual(result["evidence"][0]["quote"], "Used SQL and Python")
        self.assertEqual(draft["evidence"][0]["kind"], "practice")

    def test_changed_resume_rejects_old_review(self):
        resume = "Used Python."
        with self.assertRaisesRegex(ValueError, "简历已更改"):
            review_resume_evidence(resume + "\n", review_payload(extract_resume_evidence(resume)))

    def test_tampered_review_fields_and_unquoted_tags_are_rejected(self):
        resume = "Used SQL and Python."
        valid = review_payload(extract_resume_evidence(resume))
        changes = (
            {"labels": ["Valuation"]}, {"labels": ["SQL", "SQL"]}, {"labels": [1]},
            {"kind": "expert"}, {"kind": []}, {"included": "yes"},
            {"note": "x" * 501}, {"quote": "Invented achievement"}, {"id": "wrong"},
        )
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                payload = copy.deepcopy(valid)
                payload["evidence_edits"][0].update(change)
                review_resume_evidence(resume, payload)

    def test_duplicate_and_incomplete_review_rows_are_rejected(self):
        resume = "Used SQL.\nUsed Python."
        valid = review_payload(extract_resume_evidence(resume))
        for edits in ([], valid["evidence_edits"][:1], [valid["evidence_edits"][0]] * 2):
            with self.subTest(edits=edits), self.assertRaises(ValueError):
                review_resume_evidence(resume, {**valid, "evidence_edits": edits})


if __name__ == "__main__":
    unittest.main()
