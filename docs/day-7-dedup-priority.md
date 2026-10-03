# Day 7: deduplicated review queue

Date: 2026-10-03

## Delivered

- Normalize supplied URLs for identity: lowercase scheme/host, remove fragments and common tracking parameters, retain job-identifying query parameters such as `jobId`.
- Skip already tracked jobs before a model call. In batch mode, a repeated URL is skipped before fetching, and identical normalized posting text is prepared once even when supplied from different files or a later batch. A content fingerprint is saved in new tracker rows.
- Keep the existing tracker and job IDs for previously prepared local files. Previously tracked URL rows are also checked by their saved URL so a change in URL-ID normalization does not force a new request for the same URL.
- Write `priority_queue.md` after each batch, including when a source fails or all sources were already tracked.
- Rank new jobs with visible points for supported term length, user-stated title/location/work-mode preferences, an unambiguous quoted deadline, and employer-quoted publication recency. Unknown facts score zero. The model's free-form priority label and matching prose do not affect the queue score.

## Limits

The queue is for manual review, not a recommendation to apply or a prediction of hiring odds. A date is scored only if it can be parsed unambiguously from the posting quote. Retrieval date is not publication date. A past quoted deadline is a prompt to check live status, not proof that the role is closed. Text-identical postings from two URLs are treated as duplicates; if an employer reuses the same text for distinct openings, prepare the second with a separate output directory and verify it manually. Older tracker rows have no content fingerprint, so a changed local-file copy might not match them. Duplicates already in the tracker remain untouched, including their status and packet.

## Offline verification

Run `python -m unittest -v test_job_agent.py`. Synthetic tests cover repeated tracked batches with no further fetch or model calls, repeated text under different paths and across runs, non-colliding `jobId` values, scoring supported facts, ambiguous or absent dates, past deadlines, and partial failures retaining a queue. No live employer page, private résumé, or paid model request is used.
