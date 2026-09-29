# Eight-week project plan

## Goal

Help Canadian university students spend less time preparing accurate applications for relevant co-op roles. Start with one user's eight-month data internships; validate the workflow with a small student pilot before broadening it. The product prepares and reviews applications. It does not promise interviews or submit without the applicant's explicit review and action.

## Measures

- Median minutes from an eligible posting to a reviewed application packet.
- Fraction of extracted dates and term claims that have a supporting quote in the employer posting; count false eight-month confirmations separately.
- Fraction of suggested résumé claims accepted without factual correction.
- Number of reviewed packets that become submitted applications and subsequent interviews, recorded by version. Treat interview rates as exploratory until the sample is large enough.

## Weeks 1–2: Reliable input and evidence

1. Run the current command on at least three real postings: explicit eight-month, four-month-only, and ambiguous four-or-eight. Save only synthetic or permissioned fixtures in the repo.
2. Make extraction robust to common employer job pages; offer a clear copy-paste fallback when JavaScript or sign-in blocks the page.
3. Separate observed posting facts, inference, and unknowns. Keep publication date distinct from fetch date. Check live status manually when the page cannot establish it.
4. Add regression cases for false eight-month claims, unsupported quotes, and fabricated résumé metrics.

**Exit:** The user can review one packet without guessing where its date and term claims came from. Known four-month cases are never labeled confirmed eight-month.

## Weeks 3–4: Useful application preparation

1. Maintain a private, user-approved experience bank with canonical facts, metrics, and allowed wording. Do not commit résumés or applicant records.
2. Produce role-specific résumé bullet edits and a short application draft with evidence references, then add an editable export rather than only Markdown suggestions.
3. Support a batch of employer links with URL normalization and duplicate detection. Rank by fit, confirmed term, deadline, and employer-published recency; do not treat crawl date as posting date.
4. Offer a simple local review interface only after the command-line workflow is reliable.

**Exit:** A batch run yields a short, deduplicated queue and reviewable materials for the best roles, with no unsupported claims.

## Weeks 5–6: Workflow and feedback

1. Add a human approval step before any form preparation. Explore autofill only for sites where it can be done reliably and within their rules; leave assessments, video interviews, and final submission to the applicant.
2. Record résumé version, application date, stage, and feedback without overwriting historical transitions.
3. Compare prompts and templates on the same held-out job examples. Improve factual accuracy and time saved before optimizing for interview outcomes.

**Exit:** The user can trace an application from posting to material version and outcome, and revert to the original résumé facts.

## Weeks 7–8: Student pilot and decision

1. Ask a small group of Waterloo students to try the review flow with their own permissioned data; observe where they stop or correct the output.
2. Measure preparation time, factual corrections, repeated use, and whether users would pay for the saved time. Avoid claiming improved interview rates from a tiny sample.
3. Fix the most frequent failure mode and decide whether to focus on co-op term verification, résumé evidence, or form preparation as the product's narrow advantage.
4. Document setup, privacy, limitations, and a repeatable demo.

**Exit:** A reliable demo, pilot evidence, and a clear decision on the next product scope.

## Working rhythm

Use one scoped Codex task per change. Review the diff and test output, then merge or commit. At the end of each week, record what shipped, what failed on real postings, and the next week's top two fixes.
