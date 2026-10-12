# Architecture

## Apps

| App | Responsibility |
| --- | --- |
| `accounts` | Sign-up/login, password reset, and the email-verification state that belongs to the *account*, not the campus identity. |
| `campus` | The core domain: colleges, campus identities, hand-typed crush entries, matching, verification, notifications, privacy centre. |
| `blog` | Public guides. Bodies are staff-authored HTML, sanitized at render time. |
| `config` | Settings, the root URLconf, marketing pages, FAQ content, JSON-LD builders, the HTML sanitizer, and rate limiting. |

`config` is not registered as a Django app; its `templatetags.seo` library is
exported through `TEMPLATES["OPTIONS"]["libraries"]`.

## Domain model (campus)

- `College` — a campus/community. Crushes never cross this boundary. Has a
  public `slug` used by the shareable `/college/<slug>/` and `/join/<slug>/`
  links.
- `StudentProfile` — the private campus identity (campus + roll number is the
  identity gate). One per user. `normalized_roll_number` is the canonical key
  inside a campus.
- `CrushEntry` — a hand-typed crush. Points at internal ids and a normalized
  roll number; **never** at another student row, so a crush doesn't need an
  account and can't be a lookup.
- `PotentialMatch` — a reciprocal pair queued for review. Approval creates a
  `MutualMatch`; only that step notifies anyone.
- `MutualMatch` — a confirmed pair. `reveal` is opt-in on **both** sides.
- `Notification` — deliberately vague messages ("It's mutual", "They chose to
  reveal", roster events for reports/blocks).
- `Block`, `Report` — moderation. Blocking retires matching entries and
  pending proposals in both directions.
- `Rose` — modeled but **not implemented in the UI**. Roses are explicitly
  optional and never required for a match or reveal.
- `CollegeInvite`, `EmailVerification` — growth and account confirmation.

## Flows

1. **Register** → create secret profile (sends email-confirmation link).
2. **Campus** → manual campus picker or "add your college"; session
   pre-selection survives via `campus/campus_select` when coming from a
   `/join/<slug>/` link.
3. **Identity** → full name / roll / course / year / section (18+ enforced).
4. **Secret desk** → up to 3 active hand-typed entries (slots by priority).
5. **Seal** → reciprocal pairs become *pending proposals*; nobody is notified.
6. **Review** → a verifier approves only genuinely matching pairs; confidence
   is advisory, nothing auto-approves.
7. **Notify** → both sides get one quiet "it's mutual" alert.
8. **Reveal** → names appear only when both sides choose it; either side can
   stay anonymous or close the match.

## The verification desk

Uses the dedicated `campus.verify_potentialmatch` permission, so a moderator
can be granted exactly the reviewing job and nothing else. `reconcile` is a
staff-only maintenance sweep that re-runs the matcher.

## Rate limiting

`config.ratelimit` is a dependency-free, cache-backed fixed-window limiter:

- `register` — 10/h per IP
- login — 15/m per IP
- password reset — 5/h per IP
- `add_crush` — 30/h, `edit_crush` — 60/h, `reveal_choice` — 40/h
- `report_student` / `block_student` — 20/h per user
- `add_college` — 10/h per IP
- contact form — 5/h per IP

Counters live in `CACHES`; production should use Redis/Memcached so limits
are shared across workers. Failures are open (throttling never locks everyone
out).

## Email verification

Soft by default: the banner nudges, an unverified student keeps working. When
`EMAIL_VERIFICATION_REQUIRED=True`, `accounts.middleware.EmailVerificationMiddleware`
holds unverified non-staff accounts on a holding page (allow-listed paths,
staff, static/media and the verification endpoints are exempt). Tokens are
bound to `pk + email + timestamp` so auto-login right after sign-up does not
invalidate the emailed link.

## Public site

- Marketing pages (`config`): about, how-it-works, secret-crush, mutual-crush,
  college-crush, FAQ, safety, privacy, terms, contact (honeypot + ratelimit).
- `blog`: manager-provided publishing (drafts/future dates hidden), sanitized
  `body_html`, per-post SEO fields, related posts.
- `campus/college_landing`: public but **not** a directory; `noindex` until a
  campus has enough members. Never appears in the sitemap.