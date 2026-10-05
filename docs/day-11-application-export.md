# Day 11: reviewed application paragraph export

## Delivered

- A separate plain-text application paragraph download, containing only the saved paragraph.
- The original packet and private worksheet remain separate downloads; the worksheet button explicitly mentions private notes.
- Export requires a nonempty saved paragraph and all three manual checks. Unsaved changes disable export; editing the paragraph clears the claims check.
- The local `/api/export` endpoint independently checks the job, saved revision, checklist, and paragraph. A stale tab must reopen the job.
- Edits made during a save request remain marked unsaved; an earlier response cannot mark a different job's editor as saved.

## Boundaries

The checks record the user's review. They do not prove eligibility, posting availability, or accuracy. Export performs no model request, stores no new file on the server, and leaves the tracker status unchanged. The browser downloads UTF-8 plain text for the applicant to use and submit manually.

## Validation

Synthetic HTTP regression cases cover exact paragraph-only output, no private-note leakage, no file or status mutation, no API use, missing reviews, incomplete checks, empty drafts, stale revisions, and cross-origin rejection. Run:

```bash
python -m unittest -v test_job_agent.py test_web_ui.py test_direction_suggestions.py
node --check web/app.js
node test_web_app.cjs
```
