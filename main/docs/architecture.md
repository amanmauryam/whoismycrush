# Architecture

## Apps

| App | Responsibility |
| --- | --- |
| `accounts` | Sign-up/login, password reset, and the email-verification state that belongs to the *account*, not the campus identity. |
| `campus` | The core domain: colleges, campus identities, hand-typed crush entries, matching, verification, notifications, privacy centre. |
| `blog` | Pro Tips. CKEditor-authored guides with categories, featured posts, search and sanitized rendering. |
| `config` | Settings, the root URLconf, marketing pages, FAQ content, JSON-LD builders, the HTML sanitizer, and rate limiting. |

`config` is not registered as a Django app; its `templatetags.seo` library is
exported through `TEMPLATES["OPTIONS"]["libraries"]`.

## Domain model (campus)

- `College` — a campus/community. Crushes never cross this boundary. Has a
  public `slug` used by the shareable `/college/<slug>/` and `/join/<slug>/`
  links, plus a normalized name for duplicate detection.
- `StudentProfile` — the private campus identity. One per user. Registration
  still requires a roll number; `normalized_roll_number` is the canonical key
  inside a campus and `normalized_name` supports identity matching.
- `CrushEntry` — a hand-typed crush. The typed name/roll/course are preserved
  exactly, and the first submission is snapshotted in `original_payload` for
  audit. A missing roll is allowed. `resolved_student` is an optional, verified
  internal link to a `StudentProfile`; it is `NULL` until identity resolution is
  confident. `resolution_scoring_version` / `resolution_scored_at` record which
  policy produced the link. The entry never exposes that link to students.
- `IdentityCandidate` — explainable, staff-only evidence for a possible
  identity link. Rows are sticky: rejected/deferred candidates cannot be
  auto-bound later and must be explicitly reopened. Each row carries scoring
  version/time.
- `IdentityResolutionAudit` — append-only decisions (`auto_resolved`,
  `confirmed`, `rejected`, `deferred`, `invalidated`, `unresolvable`,
  `reopened`) with ids only, never typed names or rolls. Candidate status
  transitions are recorded separately from entry status transitions.
- `PotentialMatch` — a reciprocal pair queued for review. Approval requires both
  entries to be identity-resolved and creates a `MutualMatch`; only that step
  notifies anyone. Ineligible rows become `STALE` instead of being deleted, so
  the review history survives edits, blocks and removals. Each row carries
  `scoring_version`, `scored_at` and `invalidated_reason`.
- `MutualMatch` — a confirmed pair. `reveal` is opt-in on **both** sides.
  `notified_at` is claimed atomically so a pair is announced at most once.
- `Notification` — deliberately vague messages ("It's mutual", "They chose to
  reveal", roster events for reports/blocks). Match emails are queued in the
  same row (`email_status`, `email_attempts`, `email_sent_at`,
  `email_last_error`) and deduplicated by `dedupe_key`.
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
5. **Resolve identity** → a crush entry gains a verified internal link only
   when campus + roll are exact, the name is close, and configured hard fields
   (`IDENTITY_HARD_CONFLICT_FIELDS`, default course/year/section) do not
   conflict. Missing or conflicting evidence goes to human review. Hard fields
   are centralized in `campus/policy.py` and can be made advisory without code
   changes.
6. **Seal** → reciprocal verified pairs become *pending proposals*; nobody is
   notified.
7. **Review** → a verifier approves only genuinely matching pairs; confidence
   is advisory, nothing auto-approves.
8. **Notify** → both sides get one quiet "it's mutual" alert.
9. **Reveal** → names appear only when both sides choose it; either side can
   stay anonymous or close the match.

## The review desks

There are two separate least-privilege queues:

- `/staff/identities/` uses `campus.review_identitycandidate` to resolve
  ambiguous links before matching. Candidate details are staff-only and never
  trigger a student notification.
- `/staff/matches/` uses `campus.verify_potentialmatch` to approve reciprocal
  pairs. Approval locks both proposal rows and both entries, then re-checks that
  both are still pending, resolved to the two accounts, eligible under the
  current policy, and free of blocks or account deactivation. A required review
  note is stored on both rows.

Maintenance commands:

- `python manage.py audit_matching` — read-only report of stale proposals,
  legacy scores and email-outbox health.
- `python manage.py reevaluate_matching` — re-resolve identities and refresh
  proposals after a policy or threshold change (`--dry-run`, `--campus`).
- `python manage.py retry_notifications` — retry failed/pending match emails
  with the configured attempt limit.

`reconcile` is a staff-only maintenance sweep that re-runs identity resolution
and the matcher.

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

Verification mail uses the `EmailVerification` row as a durable transactional
outbox. Registration and resend write `email_status="pending"` and return
without waiting for SMTP; the token is generated at delivery time and is never
stored or logged. A post-commit daemon thread is a **best-effort latency
optimisation only**: it may be terminated when a WSGI process exits, so it is
not the delivery guarantee. `manage.py process_verification_emails` is the
crash-safe path and must run from cron/systemd. It retries failed rows up to
`VERIFICATION_EMAIL_MAX_ATTEMPTS`, recovers stale `sending` rows left by a
crash, and uses `VERIFICATION_EMAIL_TIMEOUT` (default 45s, long enough for a
provider's slow greeting) so a dead mail server cannot pin a worker
indefinitely. Delivery is at-least-once: a crash
between SMTP accepting a message and the final database update can duplicate
one email, but the row is never silently lost.

## Public site

- Marketing pages (`config`): about, how-it-works, secret-crush, mutual-crush,
  college-crush, FAQ, safety, privacy, terms, contact (honeypot + ratelimit).
- `blog`: Pro Tips at `/pro-tips/` with manager-provided publishing
  (drafts/future dates hidden), categories, featured lead, search, pagination,
  sanitized `body_html`, a generated table of contents, per-post SEO fields and
  related posts. CKEditor 5 is staff-only for both authoring and uploads.
- `campus/college_landing`: public but **not** a directory; `noindex` until a
  campus has enough members. Never appears in the sitemap.