# Day 3 private profile and experience bank

Date: 2026-10-01
Scope: remove candidate-specific prompt assumptions, add an evidence-bound
private profile, and verify the complete local workflow without a paid request.

## Delivered

- Added strict Pydantic models for candidate preferences and experience evidence.
- Added JSON profile loading with unknown-field rejection.
- Added duplicate evidence-ID rejection.
- Required every experience-bank `source_resume_quote` to occur in the supplied
  resume before the profile can reach the model.
- Added `profile.example.json` using only fictional data.
- Ignored private `profile*.json` files while explicitly retaining the example.
- Added the optional `--profile` CLI argument.
- Removed candidate-specific Waterloo, skill, and location assumptions from the
  production system prompt.
- Included validated preferences and experience evidence in the model input as
  data, not instructions.
- Added an offline end-to-end CLI test that writes a review packet and tracker.
- Preserved compatibility when `--profile` is omitted by using an empty profile
  with no inferred preferences.

No paid model call, live employer request, private resume, or real candidate
profile was used.

## Validation stages

### Stage 1: profile boundary

The profile parser was tested with the synthetic resume and example profile.
Valid evidence loads; a missing quote, duplicate ID, or unknown field fails
before model construction.

### Stage 2: CLI and prompt integration

The generated message contains the validated profile. The former hard-coded
candidate sentence is absent. A mocked model response exercises the actual CLI,
packet writer, and CSV tracker without network access or API charges.

### Stage 3: compatibility and documentation

Both profiled and profile-free CLI paths are covered. README setup and usage now
explain how to create a private profile and what validation it receives.

## Known boundary

Profile evidence is user-approved, and its source quote must exist in the resume.
The program cannot yet semantically prove that custom `fact` wording means
exactly the same thing as the quote. Generated non-numeric claims and application
paragraphs therefore still require human review. This remains the next factuality
task rather than being treated as solved by the profile format.

## Day 3 exit status

- [x] No candidate-specific preferences remain in the production prompt.
- [x] A private, ignored profile can carry preferences and approved evidence.
- [x] A synthetic profile is safe to commit and matches the synthetic resume.
- [x] Invalid or unsupported evidence fails before a model request.
- [x] Profiled and profile-free CLI paths work offline.
- [x] Packet and tracker output are exercised end to end.
- [x] No private data or paid request was used.
