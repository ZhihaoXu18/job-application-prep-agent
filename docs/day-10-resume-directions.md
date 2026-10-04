# Day 10: résumé-first direction suggestions

Date: 2026-10-04

## Delivered

- Local-first suggestions for at most three data-related co-op role families. Each suggestion displays exact, short résumé lines that matched at least two distinct signals. No model call, API key, employer request, or résumé persistence is needed for this step.
- Editable target-role list with explicit confirmation. Unconfirmed suggestions have no effect. Changed résumé/profile input invalidates confirmation; the backend also checks a résumé fingerprint before accepting confirmed roles.
- Confirmed roles replace only `preferences.target_roles` for a newly prepared web job. Optional location, work-mode, term, and experience-bank profile data are retained. A duplicate job still opens its existing packet, not a newly analyzed one.
- Optional manual search links for confirmed role text. Opening one sends the role text and generic `Canada co-op jobs` words to Google. It does not send the résumé; job results are not imported or verified by the app.

## Boundaries

Keyword signals can miss less conventional backgrounds and cannot prove qualifications. A user may edit in a different career direction; the tool does not reject that choice. Confirmation exists only in the current browser page, and the tool does not autonomously search job sites, log in, or submit applications.

## Verification

Offline tests cover evidence lines, absent signals, confirmation overriding only target roles, stale résumé rejection, the keyless HTTP endpoint, and passing confirmed roles into mocked job analysis. No paid model request or live employer request was used.
