# Day 6 batch input

Date: 2026-10-03
Scope: prepare multiple supplied job sources sequentially while preserving the
same evidence checks and human-review boundary used by the single-job workflow.

## Delivered

- Added `--batch-file` as a mutually exclusive alternative to `--url` and
  `--job-file`.
- Added a UTF-8 line-based manifest format with comments and blank lines.
- Supported a mixture of HTTPS URLs, absolute local paths, and paths relative to
  the manifest.
- Reused the hardened web extractor for URL entries and the same 60,000-character
  limit for copied posting files.
- Extracted the shared preparation path so single and batch jobs use the same
  analysis, evidence checks, packet rendering, and tracker behavior.
- Wrote one packet for every successfully prepared source and shared one tracker
  across the batch.
- Continued after an individual source fails, printed the failed source and
  reason, and returned exit status 1 when any failure occurred.
- Preserved the existing single-URL, single-file, feedback, profile, and
  profile-free paths.

No live URL, paid model call, real employer data, private resume, or private
profile was used.

## Offline verification

The synthetic batch manifest contains four different local postings. Its
end-to-end test verifies:

- four model-adapter calls;
- four Markdown review packets;
- four distinct tracker rows;
- a `4 prepared, 0 failed` summary;
- relative path resolution from the manifest location.

A separate partial-failure test contains one valid posting and one missing file.
It verifies that the valid packet and tracker row are retained, the missing file
is reported, later processing is not aborted, and the overall return code is 1.

The full offline suite now contains 46 tests.

## Known boundary

Day 6 deliberately preserves manifest order and does not deduplicate or rank
sources. Repeating the same source can repeat model work and may write another
packet even though the tracker keeps one job row. URL normalization, cross-source
duplicate detection, and explainable ranking belong to the next scoped change.

Batch mode can make one paid model request per unique processed source when used
with a real API key. The tool still does not submit applications or infer that a
reachable posting is open.

## Day 6 exit status

- [x] Multiple supplied postings can be prepared in one command.
- [x] URL and local-file sources can be mixed.
- [x] Relative paths are deterministic.
- [x] One failed source does not discard successful work.
- [x] Single-job behavior remains covered.
- [x] No private data, live network, or paid request was used.
