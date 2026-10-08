"""事实、期限和简历声明校验：所有岗位与简历都是合成数据。"""

import unittest

from job_agent import Analysis, Fact, check_analysis
from tests.job_agent.support import build_test_analysis, fixture


class EvidenceChecks(unittest.TestCase):
    def test_explicit_eight_month_term(self):
        resume = fixture("synthetic_resume.md")
        posting = fixture("job_explicit_eight_months.txt")
        quote = "Work term: January 4 to August 27, 2027 (8 months)."
        a = check_analysis(
            build_test_analysis(quote),
            resume,
            posting,
        )
        self.assertEqual(a.term_classification, "8_month_confirmed")
        self.assertEqual(len(a.resume_edits), 1)

    def test_four_month_only_is_low_priority(self):
        posting = fixture("job_four_months_only.txt")
        quote = "This is a 4-month internship from January 4 to April 30, 2027."
        a = check_analysis(build_test_analysis(quote), fixture("synthetic_resume.md"), posting)
        self.assertEqual(a.term_classification, "4_month_only")
        self.assertEqual(a.priority, "low")

    def test_four_or_eight_requires_confirmation(self):
        posting = fixture("job_four_or_eight_months.txt")
        quote = "Candidates may choose a 4-month or 8-month work term beginning January 2027."
        a = check_analysis(build_test_analysis(quote), fixture("synthetic_resume.md"), posting)
        self.assertEqual(a.term_classification, "variable_or_unclear")
        self.assertTrue(any("Confirm" in action for action in a.user_actions))

    def test_unstated_term_remains_unknown(self):
        a = check_analysis(
            build_test_analysis("", "variable_or_unclear"),
            fixture("synthetic_resume.md"),
            fixture("job_term_unstated.txt"),
        )
        self.assertEqual(a.term.value, "Not stated")
        self.assertEqual(a.term.source_quote, "")
        self.assertEqual(a.term_classification, "variable_or_unclear")

    def test_unsupported_quote_cannot_confirm_eight_months(self):
        a = check_analysis(
            build_test_analysis("8 months"),
            fixture("synthetic_resume.md"),
            fixture("job_term_unstated.txt"),
        )
        self.assertEqual(a.term.value, "Not stated")
        self.assertEqual(a.term_classification, "variable_or_unclear")

    def test_unsupported_facts_are_reset_and_flagged(self):
        a = build_test_analysis("", "variable_or_unclear")
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
        a = build_test_analysis("", "variable_or_unclear")
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
            build_test_analysis(quote, original_bullet="Increased revenue by 80%."),
            fixture("synthetic_resume.md"),
            fixture("job_explicit_eight_months.txt"),
        )
        self.assertFalse(a.resume_edits)
        self.assertTrue(any("omitted" in action for action in a.user_actions))

    def test_new_numeric_claim_in_rewrite_is_omitted(self):
        quote = "Work term: January 4 to August 27, 2027 (8 months)."
        a = check_analysis(
            build_test_analysis(
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
            build_test_analysis(
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
        a = build_test_analysis(quote)
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
        a = build_test_analysis("", "variable_or_unclear")
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
        a = build_test_analysis(quote)
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
        a = build_test_analysis(quote)
        a.application_paragraph = paragraph
        checked = check_analysis(
            a,
            fixture("synthetic_resume.md"),
            fixture("job_explicit_eight_months.txt"),
        )
        self.assertEqual(checked.application_paragraph, paragraph)

    def test_matching_point_with_unsupported_number_is_omitted(self):
        quote = "Work term: January 4 to August 27, 2027 (8 months)."
        a = build_test_analysis(quote)
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
        a = build_test_analysis(quote)
        a.gaps = ["The applicant lacks the required 7 years of experience."]
        checked = check_analysis(
            a,
            fixture("synthetic_resume.md"),
            fixture("job_explicit_eight_months.txt"),
        )
        self.assertFalse(checked.gaps)
        self.assertTrue(any("gap" in action for action in checked.user_actions))

    def test_analysis_rejects_invalid_closed_values(self):
        data = build_test_analysis("", "variable_or_unclear").model_dump()
        data["priority"] = "urgent"
        with self.assertRaises(ValueError):
            Analysis.model_validate(data)

        data = build_test_analysis("", "variable_or_unclear").model_dump()
        data["term_classification"] = "probably_eight_months"
        with self.assertRaises(ValueError):
            Analysis.model_validate(data)

    def test_spelled_and_numeric_term_values_are_equivalent(self):
        quote = "The eight-month placement begins in January."
        a = build_test_analysis(quote)
        a.term.value = "8 months"
        checked = check_analysis(a, fixture("synthetic_resume.md"), quote)
        self.assertEqual(checked.term.value, "8 months")
        self.assertEqual(checked.term_classification, "8_month_confirmed")
