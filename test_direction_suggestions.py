import unittest

from direction_suggestions import (
    ROLE_FAMILIES,
    get_role_family,
    apply_confirmed_directions,
    resume_fingerprint,
    suggest_directions,
)
from job_agent import CandidateProfile, ProfilePreferences
from test_job_agent import fixture


class DirectionSuggestionChecks(unittest.TestCase):
    def test_exploration_catalog_is_bounded_and_not_evidence(self):
        self.assertEqual(len({family["id"] for family in ROLE_FAMILIES}), 7)
        self.assertIsNone(get_role_family(""))
        for family in ROLE_FAMILIES:
            result = get_role_family(family["id"])
            self.assertEqual(result, family)
            self.assertNotIn("evidence", result)
            self.assertLessEqual(len(result["roles"]), 5)
            self.assertTrue(all(0 < len(role) <= 100 for role in result["roles"]))
            result["roles"].clear()
            self.assertTrue(family["roles"])

    def test_invalid_exploration_category_is_rejected(self):
        for value in ("invented", None, [], {}, 1):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "Unknown exploration"):
                get_role_family(value)

    def test_synthetic_resume_suggestions_quote_only_resume_evidence(self):
        resume = fixture("synthetic_resume.md")
        suggestions = suggest_directions(resume)
        roles = [item["role"] for item in suggestions]
        self.assertIn("Data Analyst Co-op", roles)
        self.assertIn("Business Intelligence Co-op", roles)
        self.assertLessEqual(len(suggestions), 3)
        for item in suggestions:
            self.assertGreaterEqual(len(item["evidence"]), 1)
            for quote in item["evidence"]:
                self.assertIn(quote, resume)

    def test_insufficient_evidence_does_not_invent_direction(self):
        self.assertEqual(suggest_directions("Experienced in community outreach."), [])

    def test_confirmation_replaces_only_target_roles_for_same_resume(self):
        resume = fixture("synthetic_resume.md")
        original = CandidateProfile(preferences=ProfilePreferences(
            target_roles=["Old role"], preferred_locations=["Toronto"],
        ))
        updated = apply_confirmed_directions(original, {
            "confirmed_roles": ["Data Analyst Co-op", "BI Co-op"],
            "direction_fingerprint": resume_fingerprint(resume),
        }, resume)
        self.assertEqual(updated.preferences.target_roles, ["Data Analyst Co-op", "BI Co-op"])
        self.assertEqual(updated.preferences.preferred_locations, ["Toronto"])
        self.assertEqual(original.preferences.target_roles, ["Old role"])

    def test_changed_resume_and_duplicate_roles_are_rejected(self):
        resume = fixture("synthetic_resume.md")
        with self.assertRaisesRegex(ValueError, "Resume changed"):
            apply_confirmed_directions(CandidateProfile(), {
                "confirmed_roles": ["Data Analyst Co-op"],
                "direction_fingerprint": resume_fingerprint(resume),
            }, resume + " new text")
        with self.assertRaisesRegex(ValueError, "must not repeat"):
            apply_confirmed_directions(CandidateProfile(), {
                "confirmed_roles": ["Data Analyst Co-op", "data analyst co-op"],
                "direction_fingerprint": resume_fingerprint(resume),
            }, resume)


if __name__ == "__main__":
    unittest.main()
