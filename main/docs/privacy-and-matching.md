# Privacy and matching

This document states the guarantees the product is designed around and maps
each one to where the code enforces it.

## Guarantees

1. **Your list is never shown.** `CrushEntry` rows reference internal ids and
   normalized roll numbers. No template, email, notification, API response or
   admin default exposes another student's entries.
2. **Priority is internal.** `priority` (1–3) is an internal slot key. It is
   used for list management and matching analytics only. Grep guards: it never
   appears in templates, notification text, `MATCH_BODY`/`MATCH_SUBJECT`, or
   any serialized student-facing payload.
3. **No one is told they were picked.** A proposal is never a result.
   `seal_secret` only queues `PotentialMatch` rows. Notification and email are
   sent exclusively from `approve_potential_match`.
4. **No match is announced before a human verifies it.** Matching reports
   confidence; nothing auto-approves. `campus.verify_potentialmatch` gates
   the desk.
5. **Identity is campus + roll number.** Fuzzy name matching is a *hint*; the
   verifier confirms identity and can add notes. Two people with the same roll
   in one campus (a real problem) are resolved manually, never blended by an
   auto-tiebreak that could fuse them.
6. **Reveal requires consent from both sides.** `MutualMatch.reveal_*` state
   is per side; either side can stay anonymous or close the match.
7. **No student search and no public directory.** The campus boundary protects
   matching; it never gives anyone a browseable list. `CollegeLandingView` (the
   only public college page) shows the college name and member count only, and
   is `noindex` until it has enough members.
8. **Moderation.**
   - `Block`: renames matching entries and deletes pending proposals in both
     directions; closes existing matches.
   - `Report`: private; reported profiles can be hidden/removed by reviewers.

## What is collected and where

- `User` — email (sign-in + match alert).
- `StudentProfile` — full name, roll, course, year, section, gender, DOB, plus
  the normalized roll key. Other students see **at most** the last three digits
  of a roll number at reveal time.
- `CrushEntry` — the details you type by hand, stored against internal ids.
- `BlogPost` — public content with metadata.
- Contact form — name/email/topic/message, stored in the `ContactMessage`
  table for staff triage (no email is sent); honeypot + rate limited.

## Never done

- Telling anyone they were entered as a crush.
- Announcing a match before verification.
- Showing who entered first or in which position.
- Revealing identity without both sides agreeing.
- Selling or sharing data.

## Matching rules (matching.py)

- One active entry per priority slot; max 3 (`MAX_CRUSHES = 3`).
- No self, no duplicates, no cross-campus entries.
- `normalize_roll_number` collapses case/separators only — never characters —
  so `BCA-027` and `BCA27` don't silently fuse.
- `normalize_name` drops honorifics and punctuation but preserves middle
  initials, so "Riya Sharma" never silently equals "Riya S.".
- Reciprocal pairs are deduplicated on `(crush_entry, registered_student)`.

## Analytics

Deliberately cookie-less. `ANALYTICS_ENABLED` + `ANALYTICS_DOMAIN` enable a
single Plausible script with **no crush data** sent; the flag defaults to off
and is inert unless both are set.