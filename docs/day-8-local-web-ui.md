# Day 8: local browser review interface

Date: 2026-10-03

## First usable slice

- Start `python web_ui.py` and open `http://127.0.0.1:8765/` on the same computer.
- Supply a text-based PDF, TXT, or Markdown résumé in memory, or paste résumé text; optionally upload the same validated profile JSON used by the CLI.
- Prepare one HTTPS employer URL or pasted posting using the existing extraction, model, evidence checks, packet, and tracker flow. Previously tracked jobs show their existing packet without another model request.
- Review the packet, download its Markdown, browse tracked jobs and the last CLI batch queue, and record status changes only after the user takes the corresponding real-world action.
- View previous work without an API key; new preparations require `OPENAI_API_KEY` in the server process and may incur charges.

## Privacy and limits

The HTTP server listens on loopback only. Mutating requests require a same-origin JSON request with a custom header; responses use no-store, no-sniff, same-origin resource policy, and a restrictive content security policy. Static routes are explicit, and packet reads are constrained to the selected output directory. The page does not load third-party fonts, scripts, or analytics. Uploaded résumé bytes are not saved as a separate file. Generated packets and tracker rows are still local private data and must remain outside Git.

This is a local prototype, not a hosted multi-user application. There is no login, team account, automatic submission, assessment completion, or live-open-status guarantee. Browser preparation is single-job; batch preparation remains in the CLI. The packet's headings, lists, and facts table are rendered using text-only DOM nodes, so job-posting content cannot become active HTML.

## Verification

`python -m unittest -v test_job_agent.py test_web_ui.py` covers extraction regressions plus local HTTP routing, cross-origin/custom-header rejection, missing-key behavior before fetching, in-memory upload handling, packet path containment, duplicate avoidance, and manual tracker updates. Tests use synthetic fixtures and mock the model call; no paid request is made.
