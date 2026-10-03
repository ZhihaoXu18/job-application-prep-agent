# Day 2 regression foundation

Date: 2026-09-29
Scope: synthetic evidence fixtures, offline regression coverage, and one focused
guardrail discovered through the new regression matrix.

## Delivered

- Added one entirely synthetic resume fixture.
- Added four fictional job fixtures covering explicit eight-month, four-month,
  four-or-eight-month, and unstated-term scenarios.
- Documented the evidence matrix in `tests/fixtures/README.md`.
- Expanded the offline suite from 4 tests to 14 tests.
- Added coverage for unsupported facts, missing terms, whitespace-normalized
  quotes, fabricated original resume bullets, URL normalization, fixture input,
  and the human review boundary in generated packets.
- Added a deterministic guardrail that omits a resume edit when the rewrite
  introduces a numeric claim absent from its original bullet.
- Updated the user-facing README to describe the numeric-claim guardrail and its
  limitation.

No paid model call, live job request, private resume, or real employer data was
used.

## Verification

```text
python -m unittest -v test_job_agent.py
Ran 14 tests in 0.006s
OK
```

Python compilation and `git diff --check` also pass.

## Safety behavior now locked by tests

| Condition | Expected behavior |
|---|---|
| Explicit January-to-August, eight-month quote | May remain `8_month_confirmed` |
| Four-month-only quote | Forced to `4_month_only` and low priority |
| Four- or eight-month choice | Forced to `variable_or_unclear` with a confirmation action |
| Missing term | Remains unknown and cannot confirm eight months |
| Quote missing from posting | Corresponding fact resets to `Not stated` |
| Original bullet missing from resume | Edit is omitted |
| Rewrite adds a new numeric claim | Edit is omitted |
| Rewrite preserves an existing numeric claim | Edit may remain for human review |
| Tracking query or URL fragment changes | Canonical job identity remains stable |
| Packet is generated | Human review and manual submission remain explicit |

## Remaining evidence gaps

The new numeric check is deliberately narrow. It does not prove that a revised
bullet's new non-numeric skill or causal claim is supported. Matching points,
gaps, and the application paragraph also remain instruction-bound rather than
fully grounded. Those outputs must continue to be treated as drafts.

The next implementation step should introduce a private, user-approved profile
or experience bank plus a synthetic example. Generated non-numeric claims can
then be checked against canonical evidence instead of relying only on substring
matching.

## Day 2 exit status

- [x] Synthetic fixtures contain no real applicant or employer data.
- [x] Core term scenarios are represented as reusable files.
- [x] Concrete evidence failures have focused regression tests.
- [x] Existing behavior remains compatible with the original tests.
- [x] All 14 offline tests pass.
- [x] A discovered fabricated-metric risk is blocked and documented.
