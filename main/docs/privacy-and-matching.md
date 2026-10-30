# Privacy and matching

This document states the guarantees the product is designed around and maps
each one to where the code enforces it.

## Guarantees

1. **Your list is never shown.** `CrushEntry` rows store internal ids, typed
   details, and (once verified) a private resolved-student link. No template,
   email, notification, API response or admin default exposes another student's
   entries.
2. **Priority is internal.** `priority` (1–3) is an internal slot key. It is
   used for list management and matching analytics only. Grep guards: it never
   appears in templates, notification text, `MATCH_BODY`/`MATCH_SUBJECT`, or
   any serialized student-facing payload.
3. **No one is told they were picked.** A proposal is never a result.
   `seal_secret` only queues `PotentialMatch` rows. Notification and email are
   sent exclusively from `approve_potential_match`.
4. **No match is announced before a human verifies it.** Matching reports
   confidence; nothing auto-approves. `campus.verify_potentialmatch` gates the
   match desk.
5. **Identity is resolved before matching.** A crush entry becomes linked only
   when campus + normalized roll are exact, name similarity clears the
   configured threshold, and configured hard fields do not conflict
   (`IDENTITY_HARD_CONFLICT_FIELDS`, default course/year/section). A missing or
   conflicting roll can produce staff-only `IdentityCandidate` evidence but
   never an automatic link. Reviewers use `campus.review_identitycandidate`;
   candidates are never shown to students and never trigger notifications.
6. **Reveal requires consent from both sides.** `MutualMatch.reveal_*` state
   is per side; either side can stay anonymous or close the match.
7. **No student search and no public directory.** The campus boundary protects
   matching; it never gives anyone a browseable list. `CollegeLandingView` (the
   only public college page) shows the college name and member count only, and
   is `noindex` until it has enough members.
8. **Moderation.**
   - `Block`: retires entries that resolve to (or exactly describe) the blocked
     person, marks pending proposals in both directions `STALE` (never deletes
     audit history), and closes existing matches.
   - `Report`: private; reported profiles can be hidden/removed by reviewers.

## What is collected and where

- `User` — email (sign-in + match alert).
- `StudentProfile` — full name, roll, course, year, section, gender, DOB, plus
  normalized name/roll keys. Other students see **at most** the last three
  digits of a roll number at reveal time.
- `CrushEntry` — the details you type by hand, the optional roll, and
  staff-only resolution metadata. Missing rolls are kept rather than rejected.
- `IdentityCandidate` / `IdentityResolutionAudit` — staff-only evidence and
  decisions. Audit rows store ids only, not typed names or rolls.
- `BlogPost` — public content with metadata.
- Contact form — name/email/topic/message, stored in the `ContactMessage`
  table for staff triage (no email is sent); honeypot + rate limited.

## Never done

- Telling anyone they were entered as a crush.
- Announcing a match before verification.
- Showing who entered first or in which position.
- Revealing identity without both sides agreeing.
- Selling or sharing data.

## Matching rules (matching.py, identity_resolution.py)

- One active entry per priority slot; max 3 (`MAX_CRUSHES = 3`).
- No self, no duplicates, no cross-campus entries.
- `normalize_roll_number` collapses case/separators only — never characters —
  so `BCA-027` and `BCA27` don't silently fuse.
- `normalize_name` drops honorifics and punctuation but preserves middle
  initials, so "Riya Sharma" never silently equals "Riya S.".
- Auto-resolution requires exact campus + roll, name similarity ≥ `0.88`, no
  configured hard-field conflict, and an active account. Thresholds are
  configurable with the `IDENTITY_*` settings.
- Missing/conflicting rolls, multiple plausible people, and rejected/deferred
  candidates are never auto-bound. They wait for the identity review desk.
  Reopening a closed candidate is explicit and audited.
- A resolved link is invalidated if the student disappears from the candidate
  pool or gains a hard-field conflict. A simple name correction on an
  already-verified roll keeps the link and refreshes the advisory score.
- Reciprocal pairs are deduplicated on `(crush_entry, registered_student)`.
  Rows that stop being eligible become `STALE` with a reason instead of being
  deleted.
- Approval locks both proposal rows and both entries, requires both halves to
  still be `PENDING` and resolved to the opposite student, re-runs eligibility,
  and sets `MutualMatch.notified_at` atomically before queueing notifications.
- Match emails are deduplicated per `(match, student)`. In-app notifications are
  written even when email is disabled or fails; failures are visible in the
  outbox and can be retried.
- Existing campuses, profiles, and entries are normalized/backfilled by
  migrations `campus.0004` and `campus.0005`; legacy scoring is labelled rather
  than silently re-scored.

## Analytics

Deliberately cookie-less. `ANALYTICS_ENABLED` + `ANALYTICS_DOMAIN` enable a
single Plausible script with **no crush data** sent; the flag defaults to off
and is inert unless both are set.