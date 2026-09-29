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

## Prepare an application packet

```bash
python job_agent.py --resume /path/to/your_resume.pdf --url "https://employer.example/job"
```

If the employer page is rendered by JavaScript, requires sign-in, or cannot be extracted, save the posting body in `posting.txt` and use:

```bash
python job_agent.py --resume /path/to/your_resume.pdf --job-file posting.txt
```

The script writes a Markdown review packet and `applications.csv` inside `job_agent_output/`. It uses `gpt-6-sol` through the OpenAI Responses API. The model's extracted dates and source quotes are hints for review, not independently verified evidence. Four-month-only and ambiguous terms are explicitly flagged.

The code also checks whether each quoted fact appears in the supplied posting and whether a proposed original résumé bullet appears in the supplied résumé. Unsupported dates are reset to `Not stated`; an unsupported eight-month claim is downgraded to an unclear term. This text check cannot independently confirm that the employer page is current or that a rewrite is truthful.

Run the offline evidence checks with `python -m unittest -v test_job_agent.py`.

## Record outcomes

The first run prints a job ID. After applying or receiving an update, record it:

```bash
python job_agent.py --feedback-job-id JOB_ID --outcome applied
python job_agent.py --feedback-job-id JOB_ID --outcome interview
```

Other values: `rejected`, `no_response`, `offer`. The tracker helps compare actual results over time; a small number of applications cannot establish a reliable interview-rate improvement.

## Current scope

- One posting per command; no automatic job discovery or batch application.
- No automatic submission, account login, PLUM test, or video interview.
- Text-based PDFs only; scanned résumés need OCR before use.
- Human review is required for every claim and edit.
- The OpenAI fine-tuning platform is winding down for new users; this project improves through prompt, data, and outcome evaluation rather than training new model weights.
