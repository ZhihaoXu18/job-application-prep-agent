# Day 5 job-page input tests

Date: 2026-10-02
Scope: verify static employer-page extraction and fail safely when a URL does
not provide suitable job-posting HTML.

## Delivered

- Added mocked HTTP coverage without contacting a real employer website.
- Confirmed non-HTTPS input is rejected before a request is made.
- Confirmed normal HTML is extracted while script, style, navigation, header,
  and footer content is removed.
- Confirmed the request uses the expected user agent and 20-second timeout.
- Added final-URL validation so an HTTPS input cannot silently redirect to an
  insecure HTTP destination.
- Added response content-type validation for HTML and XHTML.
- Added declared and actual two-megabyte response limits.
- Confirmed JavaScript shells with insufficient visible text use the documented
  copy-paste fallback.
- Confirmed extracted posting text is capped at 60,000 characters.
- Confirmed network timeouts and HTTP errors are surfaced rather than converted
  into apparently successful extraction.

No live network request, paid model request, real employer page, private resume,
or candidate profile was used.

## Tested page outcomes

| Input or response | Expected result |
|---|---|
| HTTP input URL | Rejected before network access |
| Normal HTTPS HTML | Main posting text returned |
| Header, navigation, script, style, or footer text | Removed |
| JSON or other non-HTML response | Rejected with text-file fallback |
| Redirect from HTTPS to HTTP | Rejected |
| Declared size above 2 MB | Rejected |
| Actual body above 2 MB | Rejected |
| JavaScript shell with short visible text | Rejected with text-file fallback |
| Network timeout | Surfaced to the caller |
| HTTP 403/500-style error | Surfaced to the caller |
| More than 60,000 extracted characters | Safely truncated |

## Known boundary

The request currently downloads the HTTP response before measuring the actual
body because `requests.get` is not operating in streaming mode. The declared
`Content-Length` check can reject a known oversized response early in processing,
but it does not prevent the initial download. A future hardening task can stream
the response with a strict byte budget.

This extractor intentionally does not execute JavaScript, sign in, bypass a
CAPTCHA, or infer that a reachable page represents an open job. Users must copy
the posting text when the static page is insufficient and verify live status on
the employer site.

## Day 5 exit status

- [x] Static HTML success path is covered.
- [x] Common parsing noise is removed and tested.
- [x] Protocol, redirect, type, size, and short-text failures are covered.
- [x] Timeout and HTTP failures remain visible.
- [x] The full offline suite passes.
- [x] No live network or private data was used.
