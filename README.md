# Job Application Prep Agent

See [the eight-week roadmap](ROADMAP.md) for the project milestones. `AGENTS.md` gives Codex the repository's factuality and privacy boundaries.

A small, local Python tool that prepares a review packet for one Canadian data internship posting. It reads a text-based résumé PDF and either an employer job URL or a copied posting. It extracts stated dates and term length, identifies fit and gaps, proposes factual résumé bullet edits, drafts a short application paragraph, and records the job in a CSV tracker.

The packet is **not an application**. Check all facts against the live employer posting, complete required assessments, and submit the application yourself. A reachable page does not prove that the role is still open. The tool does not search for new jobs or log in to applicant systems.

## Setup (macOS)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY="your-key"
```

Create an API key at [OpenAI Platform](https://platform.openai.com/api-keys). Keep it in an environment variable; do not commit it or your private résumé to GitHub. API usage can incur charges.

Create a private candidate profile from the synthetic example:

```bash
cp profile.example.json profile.json
```

Edit `profile.json` so its preferences are yours and every `source_resume_quote` exactly matches text in your supplied résumé. The profile is ignored by Git. Do not add eligibility, experience, skills, or metrics that your résumé does not support.

## Prepare an application packet

```bash
python job_agent.py \
  --resume /path/to/your_resume.pdf \
  --profile profile.json \
  --url "https://employer.example/job"
```

If the employer page is rendered by JavaScript, requires sign-in, or cannot be extracted, save the posting body in `posting.txt` and use:

```bash
python job_agent.py \
  --resume /path/to/your_resume.pdf \
  --profile profile.json \
  --job-file posting.txt
```

`--profile` is optional. Without it, the tool uses no assumed role, location, work-mode, or term preferences. With it, duplicate evidence IDs, unknown fields, and evidence quotes missing from the résumé cause a clear error before any model request.

URL input must remain on HTTPS and return HTML. Non-HTML responses, insecure redirects, pages larger than 2 MB, and pages with less than 300 characters of extracted text are rejected with a copy-paste fallback. At most 60,000 extracted characters are sent for analysis.

To prepare several postings sequentially, create a UTF-8 text manifest with one HTTPS URL or local posting path per line. Blank lines and lines beginning with `#` are ignored. Relative paths are resolved from the manifest's directory.

```text
# jobs.txt
https://employer.example/jobs/123
postings/second-role.txt
/absolute/path/to/third-role.txt
```

```bash
python job_agent.py \
  --resume /path/to/your_resume.pdf \
  --profile profile.json \
  --batch-file jobs.txt
```

Batch processing writes one review packet per newly prepared job, a shared tracker, and `priority_queue.md` in the output directory. Repeated URLs and text-identical postings are skipped within a batch and on later runs using the same tracker, so rerunning them does not make another model request. Older tracker rows lack the new content fingerprint but remain readable and are still matched by job ID or saved URL. URL normalization removes common tracking parameters but preserves identity parameters such as `jobId`. To prepare a tracked job again, use a separate `--out` directory. A failed source is reported and does not stop later sources; the command exits with status 1 if any source failed.

The review queue sorts only newly prepared jobs. Its transparent score uses your stated role, location, work-mode, and term preferences plus an unambiguous quoted deadline and employer publication date. Missing or ambiguous dates get no date points; the page retrieval date is never treated as the publication date. A past quoted deadline lowers the review score but does not prove the posting is closed. The score is an ordering aid, not an eligibility check or prediction of hiring odds. See [Day 7 details](docs/day-7-dedup-priority.md).

The script writes a Markdown review packet and `applications.csv` inside `job_agent_output/`. It uses `gpt-6-sol` through the OpenAI Responses API. The model's extracted dates and source quotes are hints for review, not independently verified evidence. Four-month-only and ambiguous terms are explicitly flagged.

The code also checks whether each quoted fact appears in the supplied posting and whether a proposed original résumé bullet appears in the supplied résumé. Unsupported dates are reset to `Not stated`; an unsupported eight-month claim is downgraded to an unclear term. This text check cannot independently confirm that the employer page is current or that a rewrite is truthful.

Additional conservative guardrails reject model output outside the allowed term and priority values. A quoted date, term, location, or work mode is reset to `Not stated` when its extracted value conflicts with the supporting quote. A proposed résumé edit is omitted when it introduces a numeric claim absent from the original bullet. Matching points and application paragraphs cannot introduce numbers absent from the supplied résumé and posting; gaps cannot introduce numeric requirements absent from the posting. Non-numeric wording still requires human review.

Run the offline evidence checks with `python -m unittest -v test_job_agent.py`.

## Record outcomes

The first run prints a job ID. After applying or receiving an update, record it:

```bash
python job_agent.py --feedback-job-id JOB_ID --outcome applied
python job_agent.py --feedback-job-id JOB_ID --outcome interview
```

Other values: `rejected`, `no_response`, `offer`. The tracker helps compare actual results over time; a small number of applications cannot establish a reliable interview-rate improvement.

## Current scope

- Single-posting and deduplicated batch preparation; no automatic job discovery or batch submission.
- No automatic submission, account login, PLUM test, or video interview.
- Text-based PDFs only; scanned résumés need OCR before use.
- Human review is required for every claim and edit.
- The OpenAI fine-tuning platform is winding down for new users; this project improves through prompt, data, and outcome evaluation rather than training new model weights.
