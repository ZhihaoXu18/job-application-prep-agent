import unittest

from job_agent import Analysis, BulletEdit, Fact, check_analysis


def analysis(term_quote: str, classification: str = "8_month_confirmed") -> Analysis:
    unknown = Fact(value="Not stated", source_quote="")
    return Analysis(
        employer="Example", title="Data Analyst", location=unknown.model_copy(),
        term=Fact(value=term_quote, source_quote=term_quote),
        start_date=unknown.model_copy(), deadline=unknown.model_copy(),
        publication_date=unknown.model_copy(), work_mode=unknown.model_copy(),
        term_classification=classification, priority="high",
        matching_points=[], gaps=[], resume_edits=[
            BulletEdit(original="Built Power BI reports", revised="Built Power BI KPI reports", reason="KPI fit")
        ],
        application_paragraph="", user_actions=[],
    )


class EvidenceChecks(unittest.TestCase):
    def test_explicit_eight_month_term(self):
        a = check_analysis(
            analysis("Term: January - August 2027"),
            "Built Power BI reports", "Term: January - August 2027",
        )
        self.assertEqual(a.term_classification, "8_month_confirmed")
        self.assertEqual(len(a.resume_edits), 1)

    def test_four_month_only_is_low_priority(self):
        a = check_analysis(analysis("4-month internship"), "Resume", "4-month internship")
        self.assertEqual(a.term_classification, "4_month_only")
        self.assertEqual(a.priority, "low")
        self.assertFalse(a.resume_edits)

    def test_four_or_eight_requires_confirmation(self):
        a = check_analysis(analysis("4 or 8 months"), "Resume", "4 or 8 months")
        self.assertEqual(a.term_classification, "variable_or_unclear")

    def test_unsupported_quote_cannot_confirm_eight_months(self):
        a = check_analysis(analysis("8 months"), "Resume", "Data analyst internship in Toronto")
        self.assertEqual(a.term.value, "Not stated")
        self.assertEqual(a.term_classification, "variable_or_unclear")


if __name__ == "__main__":
    unittest.main()
