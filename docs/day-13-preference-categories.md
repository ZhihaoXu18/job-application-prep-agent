# Day 13 — approachable candidate preferences

## User flow

1. Provide a résumé in step 1.
2. Choose a broad study/interest category, or leave it undecided.
3. Expand directions. Category presets are exploratory examples; résumé keyword hints appear in a separate section with original quotes.
4. Edit the draft (up to five roles), optionally add a preset, then explicitly confirm it.
5. Use confirmed directions for subsequent new-job preparation or open optional search links.

Seven categories cover computing, data/math/statistics, business/operations, engineering, design/product, natural/life sciences, and humanities/social sciences/communications. This is a starter catalog, not an exhaustive classification of majors or a live job database. Users can enter more specific roles themselves.

## Boundaries and data flow

`direction_suggestions.ROLE_FAMILIES` is the single catalog, supplied through `/api/state`. `/api/directions` validates the selected category and returns its presets separately from résumé hints and uploaded profile roles. Invalid identifiers are rejected. No model call, job-page fetch, résumé persistence, or tracker write occurs during expansion.

Categories are explicit exploration interests. They do not set education, evidence, eligibility, location, work mode, or term preferences. Advanced `profile.json` remains supported. Existing profile roles take priority when seeding a draft; presets can be added manually. Only confirmed role text becomes `preferences.target_roles`, with the existing résumé fingerprint guard. Other profile fields remain unchanged.

Changing the résumé, category, or profile clears confirmation and optional search links. Pending outdated responses are ignored. Editing or adding a role clears confirmation; duplicate additions are ignored and the five-role limit is enforced. Defaults preserve the previous résumé-only workflow. Nothing is automatically submitted.

## Verification

Synthetic Python tests cover catalog bounds, invalid identifiers, separation of exploration presets from evidence, profile preservation, and no-key/no-model operation. JavaScript regression tests cover catalog selection preservation, draft-only presets, advanced-profile precedence, stale responses, and the undecided fallback, alongside existing review/export/status tests. Browser QA uses synthetic résumé text only.
