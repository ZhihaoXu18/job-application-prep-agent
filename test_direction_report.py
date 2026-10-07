import copy
import unittest

from direction_report import ROLE_TEMPLATES, build_direction_report
from resume_evidence import SKILL_PATTERNS, extract_resume_evidence
from test_resume_evidence import review_payload


SYNTHETIC_RESUME = "\n".join([
    "Synthetic student example; not a real applicant.", "## Projects",
    "Built SQL reports using Excel in a fictional campus project.",
    "Coursework: Accounting and financial statements.",
    "Currently learning Python.", "No experience with Tableau or dashboards.",
    "Valuation", "This fictional text is only for offline regression testing.",
])


def report_payload(resume=SYNTHETIC_RESUME, family="finance"):
    return {**review_payload(extract_resume_evidence(resume)),
            "evidence_review_confirmed": True, "role_family": family}


def role(report, template_id):
    return next(item for item in report["reports"] if item["id"] == template_id)


class DirectionReportChecks(unittest.TestCase):
    def test_templates_use_only_recognized_labels_and_stable_unique_ids(self):
        known = {label for label, _ in SKILL_PATTERNS}
        self.assertEqual(len(ROLE_TEMPLATES), 6)
        self.assertEqual(len({item["id"] for item in ROLE_TEMPLATES}), 6)
        for template in ROLE_TEMPLATES:
            self.assertEqual(len(template["topics"]), 3)
            for _, labels in template["topics"]:
                self.assertTrue(set(labels) <= known)

    def test_requires_explicit_boolean_review_attestation(self):
        for value in (None, False, "true", 1):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "确认"):
                build_direction_report(SYNTHETIC_RESUME, {**report_payload(), "evidence_review_confirmed": value})

    def test_finance_report_has_exact_sources_and_no_private_notes(self):
        payload = report_payload()
        payload["evidence_edits"][0]["note"] = "PRIVATE NOTE NOT FOR MATCHING"
        report = build_direction_report(SYNTHETIC_RESUME, payload)
        self.assertEqual(len(report["reports"]), 3)
        self.assertEqual(report["template_version"], "2026-10-06-v1")
        analyst = role(report, "financial-analyst")
        self.assertTrue(analyst["interest_selected"])
        self.assertEqual([topic["status"] for topic in analyst["topics"]], ["course", "unknown", "practice"])
        for item in report["reports"]:
            for topic in item["topics"]:
                for row in topic["evidence"]:
                    self.assertEqual(SYNTHETIC_RESUME[row["start"]:row["end"]], row["quote"])
                    self.assertNotIn("note", row)
        self.assertNotIn("PRIVATE NOTE", str(report))
        self.assertNotIn("score", analyst)

    def test_course_and_learning_are_not_practice(self):
        resume = "Coursework: SQL and Excel.\nCurrently learning Python."
        report = build_direction_report(resume, report_payload(resume, "data"))
        analyst = role(report, "data-analyst")
        self.assertEqual(analyst["counts"]["practice"], 0)
        self.assertEqual([topic["status"] for topic in analyst["topics"]], ["course", "learning", "course"])

    def test_negation_is_not_upgraded_by_annotation(self):
        resume = "No experience with SQL or Python or Excel."
        payload = report_payload(resume, "data")
        payload["evidence_edits"][0]["kind"] = "practice"
        report = build_direction_report(resume, payload)
        analyst = role(report, "data-analyst")
        self.assertEqual(analyst["counts"]["negated"], 3)
        self.assertEqual(analyst["counts"]["practice"], 0)
        self.assertTrue(analyst["topics"][0]["evidence"][0]["type_disagreement"])

    def test_type_disagreement_does_not_upgrade_course_to_practice(self):
        resume = "Coursework: SQL and Python."
        payload = report_payload(resume, "data")
        payload["evidence_edits"][0]["kind"] = "practice"
        analyst = role(build_direction_report(resume, payload), "data-analyst")
        self.assertEqual(analyst["counts"]["practice"], 0)
        self.assertEqual(analyst["topics"][0]["status"], "mentioned")

    def test_user_can_downgrade_practice_to_course(self):
        resume = "Built SQL reports using Excel."
        payload = report_payload(resume, "data")
        payload["evidence_edits"][0]["kind"] = "course"
        analyst = role(build_direction_report(resume, payload), "data-analyst")
        self.assertEqual(analyst["topics"][0]["status"], "course")
        self.assertEqual(analyst["counts"]["practice"], 0)

    def test_mentions_are_pending_not_positive(self):
        resume = "SQL Python Excel"
        analyst = role(build_direction_report(resume, report_payload(resume, "data")), "data-analyst")
        self.assertEqual(analyst["counts"]["mentioned"], 3)
        self.assertIn("0 个有", analyst["summary"])

    def test_excluded_rows_and_deleted_labels_do_not_reappear(self):
        payload = report_payload(family="data")
        for edit in payload["evidence_edits"]:
            if "Python" in edit["labels"]:
                edit["included"] = False
            if "SQL" in edit["labels"]:
                edit["labels"] = [label for label in edit["labels"] if label != "SQL"]
        analyst = role(build_direction_report(SYNTHETIC_RESUME, payload), "data-analyst")
        self.assertEqual([topic["status"] for topic in analyst["topics"]], ["unknown", "unknown", "practice"])

    def test_undecided_does_not_infer_interest_or_rank(self):
        report = build_direction_report(SYNTHETIC_RESUME, report_payload(family=""))
        self.assertIsNone(report["role_family"])
        self.assertEqual([item["id"] for item in report["reports"]], [item["id"] for item in ROLE_TEMPLATES])
        self.assertTrue(all(not item["interest_selected"] for item in report["reports"]))

    def test_unsupported_category_and_unknown_skills_are_not_rejection(self):
        report = build_direction_report("Synthetic resume with unrecognized tools.", report_payload(
            "Synthetic resume with unrecognized tools.", "design"))
        self.assertFalse(report["supported_category"])
        self.assertEqual(report["reports"], [])
        report = build_direction_report("Synthetic resume with unrecognized tools.", report_payload(
            "Synthetic resume with unrecognized tools.", "finance"))
        self.assertTrue(all(item["counts"]["unknown"] == 3 for item in report["reports"]))

    def test_invalid_family_stale_source_and_tampering_are_rejected(self):
        payload = report_payload()
        with self.assertRaises(ValueError):
            build_direction_report(SYNTHETIC_RESUME, {**payload, "role_family": "invented"})
        with self.assertRaises(ValueError):
            build_direction_report(SYNTHETIC_RESUME + " changed", payload)
        for key, value in (("quote", "Invented quote"), ("labels", ["Valuation"])):
            edited = copy.deepcopy(payload)
            edited["evidence_edits"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                build_direction_report(SYNTHETIC_RESUME, edited)

    def test_repeated_keywords_and_lines_do_not_inflate_topic_counts(self):
        resume = "Built SQL SQL SQL reports using Excel.\nBuilt SQL reports using Excel."
        analyst = role(build_direction_report(resume, report_payload(resume, "data")), "data-analyst")
        self.assertEqual(analyst["counts"]["practice"], 2)
        self.assertEqual(sum(analyst["counts"].values()), 3)

    def test_positive_topic_still_displays_its_negative_sources(self):
        resume = "No experience with Python.\nUsed SQL.\nUsed Python in a project."
        analyst = role(build_direction_report(resume, report_payload(resume, "data")), "data-analyst")
        topic = analyst["topics"][1]
        self.assertEqual(topic["status"], "practice")
        self.assertEqual({row["kind"] for row in topic["evidence"]}, {"negated", "practice"})

    def test_omissions_remain_visible(self):
        resume = "\n".join(["Used SQL and Python."] * 45)
        report = build_direction_report(resume, report_payload(resume, "data"))
        self.assertEqual(report["omitted_fragments"], 5)


if __name__ == "__main__":
    unittest.main()
