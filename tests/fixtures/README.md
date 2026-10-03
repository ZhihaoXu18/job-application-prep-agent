# Synthetic regression fixtures

Every person, employer, email address, role, date, metric, and requirement in
this directory is fictional. These files may be committed and used in offline
tests. Never replace them with a private resume or copied private job data.

## Evidence matrix

| Scenario | Fixture or constructed mismatch | Expected result |
|---|---|---|
| Explicit January-to-August, eight-month term | `job_explicit_eight_months.txt` | `8_month_confirmed` remains confirmed |
| Four-month-only term | `job_four_months_only.txt` | `4_month_only` and low priority |
| Four- or eight-month choice | `job_four_or_eight_months.txt` | `variable_or_unclear` plus confirmation action |
| No term stated | `job_term_unstated.txt` | Unknown term and no eight-month confirmation |
| Model quote absent from posting | Constructed in `test_job_agent.py` | Fact resets to `Not stated` |
| Model invents an original resume bullet | Constructed in `test_job_agent.py` | Proposed edit is omitted |
| Rewrite adds a new numeric metric | Constructed in `test_job_agent.py` | Proposed edit is omitted |
| Rewrite preserves an existing numeric metric | Constructed in `test_job_agent.py` | Proposed edit remains available for review |
| Extracted deadline number conflicts with its quote | Constructed in `test_job_agent.py` | Deadline resets to `Not stated` |
| Location value conflicts with its quote | Constructed in `test_job_agent.py` | Location resets to `Not stated` |
| Application paragraph or match adds an unsupported number | Constructed in `test_job_agent.py` | Generated item is omitted |
| Gap adds an unsupported numeric requirement | Constructed in `test_job_agent.py` | Gap is omitted |
| Numeric and spelled-out work-term values agree | Constructed in `test_job_agent.py` | Explicit eight-month evidence remains valid |
| Model returns an unknown priority or term class | Constructed in `test_job_agent.py` | Schema validation rejects the output |
| Supported quote differs only in case/spacing | Constructed in `test_job_agent.py` | Fact remains supported |
| URL differs only by query, fragment, case, or trailing slash | Constructed in `test_job_agent.py` | Same canonical identity |

Future safety work must add cases for unsupported non-numeric claims introduced
in revised bullets and application paragraphs before those outputs are treated
as fully grounded.
