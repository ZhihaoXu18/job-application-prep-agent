# Day 12: application status timeline

## Delivered

- Preparation starts a timeline; later web and CLI status changes append transitions with their source and Toronto recording time.
- The current status and full history live together in `applications.csv` (`status_history` holds JSON). They are committed in one atomic replacement with private file permissions, avoiding mismatched history and status if writing fails.
- A local file lock serializes tracker updates and the final preparation write across CLI and web processes on macOS/Linux.
- Repeating the same state is a no-op. Corrections append a transition, preserving earlier entries.
- Older rows remain readable. Their last known state is marked as a legacy baseline; earlier events are not reconstructed. Missing event time remains unknown.
- The web editor passes a status revision; stale tabs receive a conflict and must reopen the job. The endpoint still accepts older clients without a revision.
- Damaged history is rejected without overwriting the tracker. A delayed browser response cannot replace another job's editor state.

## Boundaries

These are user-recorded events, not verification that an application was submitted or a job is open. Event time is the recording time. Résumé version and application-material version tracking remain future work. Private records stay in the ignored output directory.

## Validation

Regression tests cover timeline prefix preservation, CLI/web integration, legacy CSV rows, missing legacy times, same-status no-ops, stale revisions, malformed history, failed atomic writes, concurrent updates, and delayed browser responses. Synthetic data only; no paid API calls.

```bash
python -m unittest -v test_job_agent.py test_web_ui.py test_direction_suggestions.py test_status_history.py
node test_web_app.cjs
```
