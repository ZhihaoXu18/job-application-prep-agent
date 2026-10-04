# Day 9: manual review and editable worksheet

Date: 2026-10-04

## Delivered

- Added an editable application-paragraph field, three manual fact-check reminders, and private notes to each web packet.
- Pre-fill the editor from the generated paragraph on first open. Save later edits separately in `job_agent_output/reviews/<job_id>.json` while leaving the generated packet and tracker status unchanged.
- Persist review files with restrictive file permissions and atomic replacement. A revision token prevents a stale browser tab from overwriting a newer save.
- Offer two distinct downloads: the untouched generated Markdown packet and a working review worksheet with the user's edits, checklist, private notes, and original packet for reference.
- Keep all actions local. Saving a review does not call the model, edit the résumé, submit an application, or assert that a vacancy is open.

## Boundary

Checklist boxes mean the applicant says they performed a check; the software cannot independently verify live posting status, eligibility, or the truth of user edits. Edited text is not revalidated by the original evidence guardrails. The exported worksheet contains private notes and must not be sent to an employer as-is. The original generated packet remains available for comparison.

## Verification

`python -m unittest -v test_job_agent.py test_web_ui.py` uses synthetic fixtures and a mocked model. Web tests cover review creation without an API key, persistence, unchanged original packets, invalid checklist input, untracked IDs, 0600 file permissions, and stale-revision conflicts. No live employer or paid model request is used.
