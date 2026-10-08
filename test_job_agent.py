"""Compatibility entry point; the test bodies live in tests/job_agent/.

Keep existing commands and focused test paths working. During discovery,
the seven modules are collected directly, so this entry point adds no duplicates.
"""

import unittest

from tests.job_agent.support import (
    FIXTURES,
    build_test_analysis,
    fixture,
    html_response,
)
from tests.job_agent.test_batch import BatchChecks
from tests.job_agent.test_evidence import EvidenceChecks
from tests.job_agent.test_fetch_job import FetchJobChecks
from tests.job_agent.test_fixtures import FixtureChecks
from tests.job_agent.test_output import OutputChecks
from tests.job_agent.test_profile import ProfileChecks
from tests.job_agent.test_ranking import RankingChecks


# Existing web tests still import this fake-data helper by its old name.
make_analysis = build_test_analysis


def load_tests(loader, standard_tests, pattern):
    """Use this entry point explicitly, but do not double-run discovered tests."""
    if pattern is not None:
        return unittest.TestSuite()
    return standard_tests


if __name__ == "__main__":
    unittest.main()
