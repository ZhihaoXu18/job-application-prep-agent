# Day 4 structured output guardrails

Date: 2026-10-02
Scope: fail closed on invalid structured values and numeric claims that conflict
with or are absent from the supplied evidence.

## Delivered

- Restricted `term_classification` to `8_month_confirmed`, `4_month_only`, or
  `variable_or_unclear` at Pydantic validation time.
- Restricted priority to `high`, `medium`, or `low` at validation time.
- Rejected unknown fields from model-generated facts, bullet edits, and the
  complete analysis object.
- Normalized zero through twelve so `eight` and `8` can support the same
  work-term claim.
- Reset a supported-quote fact to `Not stated` when its extracted numeric value
  conflicts with the quote.
- Reset location and work-mode values when the claimed text is not present in
  their supporting quote.
- Omitted application paragraphs and matching points that introduce a number
  absent from the supplied resume and posting.
- Omitted gaps that introduce a numeric requirement absent from the posting.
- Preserved supported numeric claims, including the synthetic resume's 25,000
  row example.
- Kept all omissions visible as user actions instead of silently treating the
  generated text as valid.

No paid model call, live employer request, real resume, or private profile was
used.

## Tested failure cases

| Case | Result |
|---|---|
| Deadline says October 30 but quote says October 15 | Reset to `Not stated` |
| Location says Vancouver but quote says Kitchener | Reset to `Not stated` |
| Application paragraph invents a 90% result | Paragraph omitted |
| Application paragraph preserves 25,000 supported rows | Paragraph retained |
| Matching point invents a 99% result | Point omitted |
| Gap invents a seven-year requirement | Gap omitted |
| Priority is `urgent` | Pydantic validation error |
| Term classification is an unknown value | Pydantic validation error |
| Value says `8 months`, quote says `eight-month` | Accepted as equivalent |

The offline suite now contains 30 tests. It covers the profile and profile-free
CLI paths, packet and tracker creation, synthetic fixtures, work-term handling,
quote support, resume-edit metrics, and the new structured-output guardrails.

## Known boundary

Numeric comparison proves only that the same normalized number occurs in an
allowed source. It does not prove semantic entailment when the same number is
used for a different concept. Likewise, substring checking cannot prove that a
non-numeric rewritten claim has the same meaning as its source evidence.

The packet therefore remains a review artifact, not a verified application.
Non-numeric additions, causal wording, eligibility, and final application text
must still be reviewed by the applicant.

## Day 4 exit status

- [x] Closed model vocabularies are schema-enforced.
- [x] Date and term numbers cannot contradict their quotes unnoticed.
- [x] Location and work-mode values receive a direct quote consistency check.
- [x] Unsupported numbers are removed from applicant-facing draft content.
- [x] Each removal leaves an explicit review action.
- [x] New and existing offline tests pass.
- [x] No private data or paid request was used.
