# Job Application Prep Agent

See [the eight-week roadmap](ROADMAP.md) for the project milestones. `AGENTS.md` gives Codex the repository's factuality and privacy boundaries.

A small, local Python tool with a browser review interface. It prepares a review packet for a Canadian data internship posting from a text-based résumé PDF and either an employer job URL or a copied posting. It extracts stated dates and term length, identifies fit and gaps, proposes factual résumé bullet edits, drafts a short application paragraph, and records the job in a CSV tracker.

The packet is **not an application**. Check all facts against the live employer posting, complete required assessments, and submit the application yourself. A reachable page does not prove that the role is still open. The tool does not search for new jobs or log in to applicant systems.

## Setup (macOS)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY="your-key"
```

Create an API key at [OpenAI Platform](https://platform.openai.com/api-keys). Keep it in an environment variable; do not commit it or your private résumé to GitHub. API usage can incur charges.

## Local web interface

Start the browser interface from the repository directory:

```bash
python web_ui.py
```

Open [http://127.0.0.1:8765/](http://127.0.0.1:8765/) on the same computer. The server binds only to `127.0.0.1`; stop it with Ctrl+C. You can select a text-based PDF/TXT/Markdown résumé or paste résumé text, optionally upload your validated `profile.json`, then enter one HTTPS employer URL or paste a posting. The page shows the resulting review packet and existing tracker rows, and lets you record a status *after* you take the corresponding action yourself. It also displays the most recent CLI batch queue if one exists in the selected output directory.

Candidate preferences now start with seven broad study/interest categories, plus an undecided option. Expand a category to see editable exploration role presets separately from exact résumé keyword hints, then explicitly confirm up to five directions. Categories are not inferred degrees, skills, or qualification judgments. `profile.json` remains under Advanced options; its existing target roles seed the draft first, and confirmation replaces only target roles, preserving other preferences and evidence. Changing the résumé, category, or profile requires re-expansion and confirmation. See [Day 13 preference category notes](docs/day-13-preference-categories.md).

In step 1, **整理简历证据** works with only a résumé, without a posting, profile, or API key. It produces a bounded local-rule draft of recognized English/Chinese capability mentions with exact original text, character offsets, line numbers, and section context. Cards separate practice wording, coursework, learning, negation, and unqualified mentions; none prove proficiency or eligibility. Correct the type, remove recognized labels, exclude a mistaken row, or add a private note. After checking the source, confirm the page to validate its quotes against the unchanged résumé, then optionally download a private JSON draft. No résumé or annotations are written to the server, tracker, model service, or employer; refresh discards the page state. Downloaded drafts contain personal source text and notes: keep them private. They are **not** `profile.json` files and cannot yet be imported or automatically used for job matching or application generation. Missing labels are unknown, not evidence of absent ability. The direction hints now exclude clauses with recognized negation, including simple comma lists, but these heuristics are not full semantic understanding. See [Day 14 evidence draft notes](docs/day-14-resume-evidence.md).

Before preparing a job, **Suggest directions** can use local, conservative résumé-text signals to propose up to three co-op role families, each with exact résumé lines for review. This step does not need an API key, call a model, save the résumé, or search the web. Edit the proposed target-role list and explicitly confirm it; only then will those roles replace `preferences.target_roles` in the optional profile for subsequent **new** web job preparation with the same résumé. Other profile fields remain unchanged. Changing the résumé or profile invalidates confirmation, and refreshing the page discards it. Confirmed roles also produce optional Google search links; opening one sends only the confirmed role text plus `Canada co-op jobs` to Google, never the résumé. Search results are not imported automatically; copy a real employer posting into step 3. Existing tracked packets are reused rather than regenerated with a new direction. These suggestions are keyword hints, not eligibility or hiring predictions. See [Day 10 direction notes](docs/day-10-resume-directions.md).

After opening a packet, use **My manual review** to edit the application paragraph, keep private notes, and check off facts you personally verified. Saving creates a local review file under `job_agent_output/reviews/`; it never changes the original generated packet. You can download either the original packet or a working review worksheet containing your edits, checklist, private notes, and original packet. Do not send that worksheet to an employer without removing private notes and reviewing every claim. Your edits are **not automatically fact-checked**. A stale browser tab cannot overwrite a newer saved review; reopen the job if you see a revision conflict. See [Day 9 review notes](docs/day-9-manual-review.md).

The browser page works without an API key for viewing existing packets and suggesting directions. To prepare a new job, set `OPENAI_API_KEY` in the terminal before starting the server; the new request may incur a charge. Uploaded résumé bytes are parsed in memory; generated packets and the tracker are saved locally under `job_agent_output/` (ignored by Git). Do not expose the local server through a public tunnel or put private output in a tracked directory. This first interface handles one job at a time; use the CLI `--batch-file` workflow for batch preparation. See [Day 8 implementation notes](docs/day-8-local-web-ui.md).

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

The script writes a Markdown review packet and `applications.csv` inside `job_agent_output/`. It uses `gpt-5.6-sol` through the OpenAI Responses API. The model's extracted dates and source quotes are hints for review, not independently verified evidence. Four-month-only and ambiguous terms are explicitly flagged.

The code also checks whether each quoted fact appears in the supplied posting and whether a proposed original résumé bullet appears in the supplied résumé. Unsupported dates are reset to `Not stated`; an unsupported eight-month claim is downgraded to an unclear term. This text check cannot independently confirm that the employer page is current or that a rewrite is truthful.

Additional conservative guardrails reject model output outside the allowed term and priority values. A quoted date, term, location, or work mode is reset to `Not stated` when its extracted value conflicts with the supporting quote. A proposed résumé edit is omitted when it introduces a numeric claim absent from the original bullet. Matching points and application paragraphs cannot introduce numbers absent from the supplied résumé and posting; gaps cannot introduce numeric requirements absent from the posting. Non-numeric wording still requires human review.

Run the offline checks with `python -m unittest -v test_job_agent.py test_web_ui.py test_direction_suggestions.py test_status_history.py test_resume_evidence.py` and the browser-state regressions with `node test_web_app.cjs`. The web tests use a local loopback port but do not contact an employer site or make paid API requests.

### Export an application paragraph

After editing your application paragraph, complete all three manual checks and save the review. **Download application paragraph** exports only the saved paragraph as UTF-8 plain text; private notes, checklists, and the generated packet are excluded. Changing the paragraph clears the claims check, and any unsaved edit disables this export until you review and save again. The server also rejects incomplete checks, empty drafts, and stale review revisions. This is your own approval record, not automated verification. Downloading does not submit an application or change its status. **Download working worksheet (includes notes)** remains available for private work. See [Day 11 export notes](docs/day-11-application-export.md).

## Record outcomes

The first run prints a job ID. After applying or receiving an update, record it:

```bash
python job_agent.py --feedback-job-id JOB_ID --outcome applied
python job_agent.py --feedback-job-id JOB_ID --outcome interview
```

Other values: `rejected`, `no_response`, `offer`. The tracker helps compare actual results over time; a small number of applications cannot establish a reliable interview-rate improvement.

Each status change now preserves the previous state, next state, recording time (Toronto time), and whether it came from the web page or CLI. Open a job to see its **Application progress timeline**. Repeatedly saving the same status does not add an event or change its timestamp. Corrections may move back to an earlier stage; they append another transition rather than erase prior entries. Times reflect when you recorded an update, not independently verified application or interview dates. Older CSV rows display only their last known state as a legacy baseline; missing earlier history and timestamps remain unknown. The browser detects stale status revisions and asks you to reopen the job before updating. History and the current status are stored together in a new `status_history` CSV column using an atomic local write. See [Day 12 history notes](docs/day-12-status-history.md).

## Current scope

- Single-posting browser preparation and deduplicated CLI batch preparation; no automatic job discovery or batch submission.
- No automatic submission, account login, PLUM test, or video interview.
- Text-based PDFs only; scanned résumés need OCR before use.
- Human review is required for every claim and edit.
- The OpenAI fine-tuning platform is winding down for new users; this project improves through prompt, data, and outcome evaluation rather than training new model weights.
