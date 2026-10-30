# Uncommitted Changes Report

**Project:** WhoIsMyCrush (`main/`)  
**Report date:** 27 October 2026  
**Baseline:** current `HEAD`  
**Commit status:** nothing committed; all changes below are in the working tree.

## 1. Executive summary

The working tree contains the admin identity-review and match-review UX overhaul, plus supporting scoring, notification, audit, migration, security, test and documentation work.

Current working-tree size:

- **25 modified tracked files**
- **7 new untracked code/support files**
- **1 new untracked report file** (this document)

Latest verification:

- `python manage.py test campus accounts --verbosity=1` — **128 tests pass**
- `python manage.py check` — no issues
- `node --check static/js/board.js` — no syntax errors
- `git diff --check` — no whitespace errors (only Windows LF/CRLF warnings)

The two review queues are now separate, permission-gated staff desks:

- `/staff/` — combined staff dashboard
- `/staff/identities/` — ambiguous identity review
- `/staff/matches/` — reciprocal match review

Django admin remains available for superusers and maintenance work.

---

## 2. Changes made in this session

These are the features/improvements added or corrected during the latest session.

### 2.1 Weighted identity score breakdown — Added

- Identity candidate evidence now stores per-component points:
  - roll number
  - name similarity
  - nickname
  - course
  - year
  - section
  - department
- The identity detail page renders the breakdown as labelled progress bars with `points / maximum`.
- Existing/legacy candidates that have no component data show a safe fallback asking staff to re-run resolution.
- Component labels and maximum weights are centralised in `campus/identity_resolution.py`.

Files:

- `campus/identity_resolution.py`
- `campus/views.py`
- `templates/campus/identity_review_detail.html`
- `static/css/pages.css`
- `campus/tests.py`

### 2.2 Distinct message/toast styles — Updated

- Success, warning, info and error messages now have distinct colour styles.
- Error messages use `role="alert"`; other messages use `role="status"`.
- Previously success and warning both appeared yellow.

Files:

- `templates/base.html`
- `static/css/board.css`

### 2.3 Admin form busy/loading state — Added

- Staff forms marked with `data-busy-form` now:
  - disable submit buttons during submission;
  - show `Working...` on the active button;
  - block double submits;
  - restore labels/button state when returning through browser history.
- Applied to identity decisions, identity re-run/unresolvable forms, bulk re-run and match approval/rejection.

Files:

- `static/js/board.js`
- `templates/campus/identity_review.html`
- `templates/campus/identity_review_detail.html`
- `templates/campus/pending_match_detail.html`

### 2.4 Defer confirmation — Added

- The Defer action now asks for confirmation before parking a candidate, matching the confirm/reject safety pattern.

File:

- `templates/campus/identity_review_detail.html`

### 2.5 Staff navigation improvements — Added

- Superusers now get a direct **Django admin** link in the staff navigation.
- Active staff tabs now expose `aria-current="page"` for assistive technology.

File:

- `templates/campus/staff_nav.html`

### 2.6 `reconcile` permission hardening — Updated

- `reconcile/` previously required only `is_staff`.
- It now requires superuser or `campus.verify_potentialmatch` permission.
- Unauthorised staff receive an error message and are redirected.

File:

- `campus/views.py`
- `campus/tests.py`

### 2.7 One-sided proposal pagination — Added

- Previously only the first 20 one-sided proposals were shown while the count implied all were visible.
- They are now paginated using `upage`, with an accurate “X–Y of Z” range and Previous/Next controls.
- Reciprocal pair pagination remains independent (`page`).

Files:

- `campus/views.py`
- `templates/campus/pending_matches.html`
- `campus/tests.py`

### 2.8 Additional tests — Added

Five new tests were added:

1. Score evidence contains weighted components and totals match.
2. Identity detail renders the weighted breakdown.
3. Reconcile requires match-review permission.
4. One-sided proposals paginate.
5. End-to-end staff flow: dashboard → identity confirmations → match queue → approval → notifications.

Files:

- `campus/tests.py`

---

## 3. Previously uncommitted implementation completed in the working tree

These features were already present in the uncommitted working tree before this session. They are listed here so the report covers all uncommitted code.

### 3.1 Staff dashboard and navigation — Added

- New combined staff dashboard at `/staff/`.
- Metrics for:
  - reciprocal pending pairs;
  - blocked conflicts;
  - stale proposals;
  - identity reviews needing attention;
  - all unresolved identities.
- Queue previews and permission-aware links.
- Shared staff navigation across dashboard, identity review and match review.
- Staff link in the main site navbar for authorised users.
- Permission-aware access:
  - identity desk requires `campus.review_identitycandidate`;
  - match desk requires `campus.verify_potentialmatch`.

Files:

- `campus/views.py`
- `campus/urls.py`
- `templates/campus/staff_dashboard.html` (new)
- `templates/campus/staff_nav.html` (new)
- `templates/components/navbar.html`
- `static/css/pages.css`

### 3.2 Identity review desk — Added/Updated

- Dedicated ambiguous-identity queue at `/staff/identities/`.
- Side-by-side comparison of:
  - the typed crush entry;
  - the selected registered student.
- Candidate shortlist with:
  - confidence;
  - name similarity;
  - roll match/conflict;
  - hard conflicts;
  - block status;
  - eligibility.
- Candidate actions:
  - confirm identity;
  - reject candidate;
  - defer candidate;
  - reopen closed candidate.
- Entry actions:
  - mark unresolvable;
  - re-run safe resolution.
- Safe bulk re-run (never confirms identities automatically).
- Audit trail with actor, notes and status transitions.
- Search/filter/sort/pagination.
- Required human-readable reason for decisions.
- Old basic identity table replaced by the richer review queue.
- Original typed payload snapshotted in `CrushEntry.original_payload` for later audit.

Files:

- `campus/views.py`
- `campus/identity_resolution.py`
- `campus/forms.py`
- `campus/models.py`
- `templates/campus/identity_review.html`
- `templates/campus/identity_review_detail.html`
- `static/css/pages.css`

### 3.3 Match review desk — Added/Updated

- Reciprocal pair queue at `/staff/matches/`.
- One row represents both directions of a pair.
- Both students’ registered details and typed entries are shown side by side.
- Current verdict includes:
  - stored confidence;
  - current confidence;
  - reasons;
  - blockers;
  - hard conflicts;
  - block status.
- Decision history and audit notes.
- Approve/reject actions require a reason.
- Approval notifies both students; rejection notifies nobody.
- Search, campus filter, blocked-only filter, sorting and pagination.
- Stale proposals are shown as history and cannot be approved.
- One-sided proposals are clearly separated and cannot be approved.
- Old single-table review view replaced by pair cards/detail workflow and dedicated history sections.

Files:

- `campus/views.py`
- `campus/services.py`
- `campus/matching.py`
- `campus/forms.py`
- `templates/campus/pending_matches.html`
- `templates/campus/pending_match_detail.html`
- `static/css/pages.css`

### 3.4 Matching and identity scoring policy — Added/Updated

- Versioned matching policy: `match-v2`.
- Versioned identity scoring: `identity-v2`.
- Shared hard/soft conflict policy in `campus/policy.py`.
- Configurable hard conflict fields:
  - `MATCH_HARD_CONFLICT_FIELDS`
  - `IDENTITY_HARD_CONFLICT_FIELDS`
- Configurable matching threshold and roll requirement.
- Stale proposal status (`STALE`) instead of deleting history.
- Scoring version/timestamp stored on proposals, entries and candidates.
- Explainable evidence for identity candidates.
- Late-registration recovery for previously unresolved entries.
- Re-evaluation and audit commands.

Files:

- `campus/policy.py` (new)
- `campus/matching.py`
- `campus/identity_resolution.py`
- `campus/models.py`
- `config/settings.py`
- `campus/management/commands/audit_matching.py` (new)
- `campus/management/commands/reevaluate_matching.py` (new)

### 3.5 Approval safety — Updated

- Approval locks both proposal rows and both entries.
- Re-checks:
  - both proposals are still pending;
  - both entries still resolve to the opposite student;
  - no block exists;
  - both accounts are active;
  - both entries pass the current matching policy.
- Prevents self-pairs and cross-campus pairs.
- Stores required admin notes on both rows.
- Creates only one mutual match and one notification per student.
- Rejecting closes both halves and notifies nobody.

Files:

- `campus/services.py`
- `campus/views.py`
- `campus/tests.py`

### 3.6 Notification email outbox — Added

- Notifications now carry email outbox state:
  - `email_status`
  - `email_attempts`
  - `email_last_error`
  - `email_sent_at`
  - `email_last_attempt_at`
  - `dedupe_key`
- In-app notifications are still written when email is disabled or fails.
- Failed/pending emails can be retried from Django admin or a management command.
- Duplicate notifications are prevented with `dedupe_key`.

Files:

- `campus/models.py`
- `campus/services.py`
- `campus/admin.py`
- `campus/management/commands/retry_notifications.py` (new)

### 3.7 Security and validation hardening — Added/Updated

- Safe `next` redirects after resend-verification; external URLs are rejected.
- Crush entries must be on the student’s own campus.
- Admin review notes are required and normalised.
- `PotentialMatchAdmin` now requires match-review permission for view/change.
- Superuser-only delete permission on potential matches.
- `reconcile` now requires match-review permission.
- Blocking and account deletion mark pending proposals `STALE` instead of deleting audit history.
- `PotentialMatch.is_resolved` now correctly treats `STALE` as unresolved.
- MutualMatch consent swaps correctly when user A/B ordering is normalised.

Files:

- `accounts/views.py`
- `accounts/tests.py`
- `campus/forms.py`
- `campus/models.py`
- `campus/services.py`
- `campus/admin.py`
- `campus/views.py`
- `campus/identity_resolution.py`

### 3.8 Django admin maintenance improvements — Updated

- Potential-match admin:
  - scoring version/time;
  - stale reason;
  - safer permissions;
  - better select-related.
- Identity-candidate admin:
  - scoring fields;
  - reopen action;
  - candidate status transition audit.
- Notification admin:
  - email outbox columns/filters;
  - retry-email action.
- Mutual-match admin:
  - notification/created filters;
  - read-only timestamps.
- Audit admin:
  - candidate status transition columns.

File:

- `campus/admin.py`

### 3.9 Data migration — Added

`campus.0005_crushentry_original_payload_and_more` adds and backfills:

- first-submission snapshots (`original_payload`);
- `STALE` proposal status;
- scoring versions/timestamps;
- candidate status transitions in identity audit;
- notification email outbox fields;
- legacy labels for existing resolved entries;
- `skipped` email status for notifications created before the outbox existed.

Files:

- `campus/migrations/0005_crushentry_original_payload_and_more.py` (new)
- `campus/models.py`

### 3.10 Documentation — Updated

- Daily admin workflow now points to `/staff/` instead of Django admin.
- Identity/match review instructions updated.
- Deployment notes added for the outbox and migration.
- Architecture and privacy docs updated for stale proposals, scoring versions, policy fields and email outbox.
- Maintenance commands documented:
  - `audit_matching`
  - `reevaluate_matching`
  - `retry_notifications`

Files:

- `docs/admin-guide.md`
- `docs/architecture.md`
- `docs/deployment.md`
- `docs/privacy-and-matching.md`

---

## 4. Feature-level added / updated / removed

### Added

- Combined staff dashboard.
- Shared staff navigation.
- Side-by-side identity review.
- Candidate shortlist and eligibility status.
- Candidate confirm/reject/defer/reopen actions.
- Safe bulk identity re-run.
- Reciprocal pair-based match review.
- Search/filter/sort/pagination on both queues.
- Weighted identity score breakdown.
- Per-component score evidence.
- Busy/loading form state and double-submit protection.
- Distinct success/warning/info/error toasts.
- Superuser Django admin link.
- One-sided proposal pagination.
- Stale proposal status and reasons.
- Scoring version/timestamps.
- First-submission payload snapshots.
- Candidate status transition audit.
- Notification email outbox and retry.
- Central policy module.
- Management commands for audit/re-evaluation/retry.
- Migration `campus.0005`.
- Five new tests this session; 128 total tests.

### Updated

- Identity review UI replaced with queue + evidence + decision workflow.
- Match review UI replaced with pair cards + detail decision workflow.
- Admin guide now directs daily review away from Django admin.
- Approval re-validates identity, policy, blocks and account state under locks.
- Blocking/account deletion retire proposals as `STALE` rather than delete them.
- `PotentialMatch.is_resolved` semantics corrected for stale rows.
- `reconcile` requires match-review permission.
- Admin review notes are required and normalised.
- Crush entry validation now enforces same-campus targets.
- Verification resend now rejects external `next` URLs.
- Notification handling now records email state and deduplicates.
- Django admin list/filter/action ergonomics improved.
- Docs and deployment instructions updated.

### Removed / Replaced

- Old basic identity table UI was replaced by the fuller review desk.
- Old pending-match table UI was replaced by pair cards, detail pages and history sections.
- Direct Django-admin-first workflow was replaced in the admin guide by the staff desk. Django admin itself was **not removed**.
- Pending proposals are no longer deleted during block/account cleanup; they become `STALE` for audit history.
- `reconcile` no longer accepts arbitrary `is_staff` users without match-review permission.
- Inline one-sided proposal list was replaced by a paginated table.
- No new frontend framework or dependency was introduced.

---

## 5. Data/schema changes

- `CrushEntry`:
  - `resolution_scoring_version`
  - `resolution_scored_at`
  - `original_payload`
- `PotentialMatch`:
  - `STALE` status
  - `invalidated_reason`
  - `scoring_version`
  - `scored_at`
  - new index on `crush_entry + status`
- `IdentityCandidate`:
  - `scoring_version`
  - `scored_at`
- `IdentityResolutionAudit`:
  - `candidate_from_status`
  - `candidate_to_status`
- `Notification`:
  - `dedupe_key`
  - `email_status`
  - `email_attempts`
  - `email_last_error`
  - `email_sent_at`
  - `email_last_attempt_at`
  - new index on `email_status + created_at`
- `MutualMatch`:
  - save-time normalisation also swaps consent flags correctly.

Migration:

- `campus/migrations/0005_crushentry_original_payload_and_more.py`

---

## 6. Security and privacy impact

- Staff routes remain permission-gated server-side.
- Identity evidence stays staff-only; students never see candidate or score data.
- Match approval is still the only path that creates a mutual match or notifies students.
- Approval re-validates under database locks.
- Blocking and deletion preserve audit history instead of deleting proposals.
- External redirects from resend-verification are rejected.
- Django admin retains superuser access but daily review uses least-privilege staff desks.
- No student-facing data model or priority field was exposed.

---

## 7. UI/UX/accessibility changes

- Responsive staff dashboard and review layouts.
- Side-by-side comparison on identity detail.
- Pair cards on match review.
- Status chips, stamps, score pills and filter tags.
- Empty states and actionable notices.
- Search/filter/sort/pagination.
- Confirmation dialogs for destructive/irreversible actions.
- Busy states while submitting.
- ARIA roles for messages; `aria-live` region.
- `aria-current="page"` on active staff tabs.
- Reduced-motion support remains in the existing design system.
- Existing paper/ink design system reused; no new frontend stack.

---

## 8. Tests and verification

Commands run:

```powershell
python manage.py test campus accounts --verbosity=1
python manage.py check
node --check static/js/board.js
git diff --check
```

Results:

- **128 tests passed**
- Django system check: no issues
- JavaScript syntax: OK
- Diff whitespace check: OK (only line-ending warnings)

New tests added this session:

1. `test_candidate_evidence_records_weighted_score_components`
2. `test_detail_renders_weighted_score_breakdown`
3. `test_reconcile_requires_match_review_permission`
4. `test_one_sided_proposals_are_paginated`
5. `test_staff_can_resolve_identities_and_approve_the_match`

---

## 9. File inventory

### Modified tracked files (25)

- `accounts/tests.py`
- `accounts/views.py`
- `campus/admin.py`
- `campus/forms.py`
- `campus/identity_resolution.py`
- `campus/matching.py`
- `campus/models.py`
- `campus/services.py`
- `campus/tests.py`
- `campus/urls.py`
- `campus/views.py`
- `config/settings.py`
- `docs/admin-guide.md`
- `docs/architecture.md`
- `docs/deployment.md`
- `docs/privacy-and-matching.md`
- `static/css/board.css`
- `static/css/pages.css`
- `static/js/board.js`
- `templates/base.html`
- `templates/campus/identity_review.html`
- `templates/campus/identity_review_detail.html`
- `templates/campus/pending_match_detail.html`
- `templates/campus/pending_matches.html`
- `templates/components/navbar.html`

### New untracked code/support files (7)

- `campus/policy.py`
- `campus/migrations/0005_crushentry_original_payload_and_more.py`
- `campus/management/commands/audit_matching.py`
- `campus/management/commands/reevaluate_matching.py`
- `campus/management/commands/retry_notifications.py`
- `templates/campus/staff_dashboard.html`
- `templates/campus/staff_nav.html`

### Report file

- `docs/uncommitted-changes-report.md` (this document)

---

## 10. Notes and limitations

- **Nothing has been committed.** This report describes the working tree only.
- The working tree already contained a large uncommitted admin-review implementation before this session; this report separates “this session” changes from that earlier baseline.
- Legacy candidates without component evidence show a fallback until identity resolution is re-run.
- Migration `campus.0005` must be applied and the post-deploy audit commands run in deployment.
- Confidence scores remain advisory; staff approval is still required for a mutual match.
- Django admin is preserved for maintenance but is no longer the documented daily review path.
