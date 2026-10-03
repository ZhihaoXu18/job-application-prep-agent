# Day 1 baseline

Date: 2026-09-29
Scope: local setup, offline verification, and a baseline risk review. No paid
model request and no private applicant or job data were used.

## Product baseline

The current repository is a single-user command-line proof of concept for
preparing, not submitting, Canadian co-op applications. Its main flow is:

1. Read a text-based PDF, Markdown, or text resume.
2. Read one employer URL or one copied job posting.
3. Ask the OpenAI Responses API for a structured `Analysis`.
4. Apply deterministic checks to posting quotes, work-term classification, and
   the existence of each proposed original resume bullet.
5. Write a Markdown review packet and a current-state CSV tracker.
6. Leave review, assessments, and final submission to the applicant.

The code is intentionally narrow. It does not discover jobs, log in to an ATS,
fill assessments, answer video interviews, or submit applications.

## Environment

- macOS
- Python 3.13.2
- Virtual environment: `.venv`
- OpenAI SDK: 3.22.1
- Pydantic: 2.13.5
- pypdf: 6.19.0
- requests: 2.34.2
- Beautiful Soup: 4.15.0
- `OPENAI_API_KEY`: not configured in the verification shell

Setup command:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## Verification results

| Check | Result |
|---|---|
| Python compilation of `job_agent.py` and `test_job_agent.py` | Pass |
| `python -m unittest -v test_job_agent.py` | Pass: 4 of 4 |
| CLI `--help` | Pass |
| Missing API credential path | Pass: exits with code 1 and a credential message |
| Live model generation | Not run; avoids an unapproved paid request |
| Live employer-page extraction | Not run; scheduled after synthetic fixtures establish expected behavior |

The existing tests cover an explicit January-to-August term, a four-month-only
term, a four-or-eight-month term, and an unsupported eight-month quote. They do
not yet exercise file input, page extraction, packet rendering, tracker writes,
or a complete preparation run.

## Baseline issues

### P1: generated claims are not fully evidence-checked

`check_analysis` verifies that a proposed edit's `original` text appears in the
resume, but it does not verify that the `revised` text preserves every fact.
`matching_points`, `gaps`, and `application_paragraph` also rely on the model
instruction rather than a deterministic evidence check. A fluent response can
therefore still introduce an unsupported skill, metric, or implication.

**Target:** generated claims reference approved resume evidence, and ungrounded
claims are removed or explicitly marked for review.

### P1: user facts and preferences are embedded in the prompt

Waterloo Statistics, tools, and location preferences are hard-coded in
`make_analysis`. This makes the program look reusable while it actually follows
one applicant's assumptions. It also makes approved facts difficult to version.

**Target:** load an ignored, user-owned profile or experience bank and keep a
synthetic example in the repository.

### P1: there is no offline end-to-end regression test

The test suite directly constructs `Analysis` objects. It does not prove that
CLI validation, input handling, packet output, or tracker behavior work together.
The model call should be replaceable with a deterministic fake for tests so no
unit test makes a paid request.

**Target:** one synthetic end-to-end test exercises preparation from input files
through packet and tracker output.

### P1: important structured values are weakly typed

`term_classification` and `priority` are plain strings in the Pydantic model.
Only term classification receives a manual allow-list check; an unexpected
priority can reach the output unchanged.

**Target:** represent closed vocabularies with `Literal` or enums and reject
invalid model output at schema validation time.

### P2: static page extraction has limited failure coverage

`fetch_job` supports ordinary server-rendered HTML and correctly recommends a
copy-paste fallback for short output. There are no tests for redirects, oversized
pages, non-HTML responses, JavaScript shells, timeouts, or request failures.

**Target:** deterministic tests cover supported HTML and each documented fallback
without depending on live employer websites.

### P2: the tracker loses state history and artifact versions

Feedback updates overwrite `status` and `outcome_at`. The tracker does not record
each transition, the source resume version, or the prompt/application packet
version. Repeated preparation of an existing job can also create another packet
without associating that packet with a new tracker version.

**Target:** keep append-only transitions and enough version metadata to reproduce
which materials were reviewed and submitted.

### P2: dependency compatibility is not reproducible

Every requirement uses only a lower bound. Day 1 installed the newest available
packages, including OpenAI 3.22.1, but the repository does not record a tested
upper bound or lock file. A future clean install could behave differently.

**Target:** document the supported Python range and introduce a reproducible,
reviewable dependency strategy after compatibility is verified.

### P2: batch preparation and deterministic ranking do not exist

The CLI intentionally handles one posting at a time. URL normalization is used
for job identity, but there is no batch input, cross-input duplicate report, or
explainable queue ordered by term, deadline, fit, and location.

**Target:** defer implementation until the evidence boundary and offline tests
are reliable; do not scale unreliable generation.

## Day 1 exit status

- [x] Repository checked out in the working directory.
- [x] Isolated Python environment created.
- [x] Declared dependencies installed.
- [x] Existing unit tests and syntax checks pass.
- [x] CLI and missing-credential paths checked.
- [x] Current architecture and risks recorded.
- [x] No private data committed and no paid API request made.

## Day 2 starting point

Build synthetic fixtures and expand the evidence regression matrix before
changing production behavior. Start with explicit eight-month, four-month-only,
four-or-eight-month, unstated-term, unsupported-quote, and fabricated-metric
cases. Every failure should become a focused regression test.
