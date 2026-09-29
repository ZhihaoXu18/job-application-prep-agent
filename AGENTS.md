# Repository guidance

This is an evidence-bound application preparation tool for Canadian student co-ops. Read `ROADMAP.md` when planning milestones and `README.md` when changing setup or user-facing behavior.

- Never invent applicant experience, metrics, eligibility, posting dates, deadlines, or an eight-month term. Preserve an explicit unknown state when evidence is missing.
- Keep personal résumés, application records, API keys, and copied private job data out of the repository. Use synthetic fixtures for tests.
- Do not add automatic application submission, assessment completion, or video interview responses. Any form preparation must leave the applicant a clear review step.
- Prefer small, reviewable changes. Run `python -m unittest -v test_job_agent.py` for changes to extraction, classification, or packet output; add focused regression cases for concrete failures.
- Check the current OpenAI SDK documentation before changing API calls. Do not make paid API requests in unit tests.
