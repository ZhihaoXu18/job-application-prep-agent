# Day 14 — structured résumé evidence draft

## Shipped scope

The first evidence step works independently of job input and optional preferences. It uses local rules rather than a paid model call. This is a bounded capability-mention ledger, not a complete résumé parser, calibrated skill assessment, or personalized job recommendation engine.

Each row contains a stable ID bound to the résumé fingerprint and original character span, exact quote, line number, section context, recognized labels, wording kind, inclusion flag, private note, and review flag. Kinds distinguish `practice`, `course`, `learning`, `negated`, and `mentioned`. Practice describes wording in the source; it never asserts proficiency or employment eligibility. Common English/Chinese labels include data/software tools and a small finance vocabulary.

## Extraction and limitations

`resume_evidence.py` splits source lines into clauses while preserving offsets and numeric commas. Recognized contrasting conjunctions delimit claims. Conservative negation takes precedence, followed by learning, coursework/context, practice-action wording, and unqualified mention. Simple comma lists inherit negation or learning context. Unknown, unsupported skills remain absent from the ledger, not labeled missing. Output is bounded to 40 rows and 2,000 characters per quote; omitted fragments are reported rather than silently truncated into partial evidence.

This does not resolve all negation scope, double negatives, actor identity, proficiency, multilingual synonyms, PDF layout, or sentence semantics. Course/project context may be ambiguous. Users can correct classifications or exclude false detections, but cannot rewrite source quotes or add capability labels unsupported by the recognized source. Arbitrary notes are review annotations, never facts. Unrecognized skills cannot yet be manually added; retain the original résumé for review.

Direction hints share the clause/negation gate, so examples such as “No experience with SQL or Python” no longer create positive hints. Non-negated coursework and learning can still produce keyword hints; they are not upgraded to practiced skills. This change does not replace the fixed interest catalog or merge interest with capability scoring.

## Review and privacy

`POST /api/resume-evidence` returns an in-memory draft. `POST /api/resume-evidence/review` rebuilds it from the supplied résumé, checks its fingerprint and exact source spans, requires every row once, and accepts only valid kind, label subset, inclusion flag, and bounded note edits. Unsupported fields, invented quotes/labels, duplicate rows, and stale résumés are rejected. The result is user-reviewed annotation, not verified truth. Existing same-origin/custom-header guards apply.

The browser requires source attestation for confirmation and invalidates it after edits. Changed résumés clear both drafts and review state; stale extraction/review responses are ignored. Interest/profile changes do not invalidate this résumé-only ledger. Nothing is persisted server-side or implicitly added to the application profile, model input, or tracker. Optional JSON download stays under the user's control; it includes private source quotes/notes and is ignored by Git if placed in the checkout. Refresh loses the page state. Import and downstream use are intentionally not implemented in this milestone.

## Acceptance checks

- Synthetic English/Chinese practice, coursework, learning, negation, and bare mentions remain distinct.
- Every quote maps exactly to the source character span, including CRLF and numeric commas.
- Recognized negative statements do not create positive direction hints; explicit contrasting positive clauses can.
- Unknown skills, output bounds, source tampering, unsupported labels, incomplete/duplicate edits, and stale fingerprints are handled conservatively.
- HTTP extraction/review require neither key nor posting and create no output files.
- Frontend editing clears review/download readiness; delayed results cannot overwrite changed source or annotations.

Next: source-grounded role templates and explainable direction reports. Reviewed JSON is a foundation, not yet a matching input.
