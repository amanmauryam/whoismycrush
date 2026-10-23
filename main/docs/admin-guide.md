# Admin guide

This is the operating manual for whoever runs WhoIsMyCrush. Every task below
answers the same three questions: **when** to do it, **why** it matters, and
exactly **what to click or run**.

The one rule that outranks everything else: **no match is announced until a
human approves it.** The review desk is therefore the most important admin
screen in the product. A slow or careless queue directly breaks the promise the
site makes to students.

---

## 1. Roles and access

There are two different admin surfaces:

| Surface | URL | Who gets in | What it is for |
| --- | --- | --- | --- |
| Django admin | `/admin/` | `is_staff=True` | Raw model management: campuses, students, entries, blog, reports, users. |
| Verification desk | `/staff/matches/` | `is_superuser` **or** (`is_staff` **and** `campus.verify_potentialmatch`) | The safe, side-by-side match review screen with notes. |

Recommended roles:

| Role | Access | Give them | Do not give them |
| --- | --- | --- | --- |
| Owner / superuser | Everything | Full admin, settings, users | Nothing extra; keep the account count small |
| Match verifier | Review desk only | `is_staff` + `campus.verify_potentialmatch` | Superuser, blog, user management |
| Content editor | Pro Tips only | Blog category/post permissions | Student, match, report, or user access |
| Ops / engineering | Terminal | Deploy, backups, commands | Routine student-data access |

### Create a verifier (do this once per person)

1. Open `/admin/auth/user/add/`.
2. Set a username and a strong password.
3. Tick **Staff status**. Leave **Superuser status** unticked.
4. Save, then under **Permissions** add
   `Campus | Potential match | Can approve or reject potential matches`.
5. Save again.

Why: the dedicated permission lets a moderator do exactly one job. It also
means every approval records a real `verified_by` user, which is the only audit
trail the product has.

Never share a login between people. If someone leaves, deactivate their user
immediately; do not delete it, because deleted users erase the `verified_by`
link from past approvals.

---

## 2. First-time setup

Run these once on a new environment, in this order:

```powershell
python manage.py migrate                 # create the schema
python manage.py seed_posts              # Pro Tips content (idempotent)
python manage.py seed_colleges           # optional starter campus list
python manage.py createsuperuser         # owner account
python manage.py collectstatic --noinput # CKEditor + site assets for WhiteNoise
python manage.py check_email --to you@example.com
```

Why each step:

- `migrate` — nothing works before the tables exist.
- `seed_posts` — the public Pro Tips page is otherwise an empty directory.
- `seed_colleges` — gives the campus picker a starter list. Safe to re-run.
- `createsuperuser` — the only account that can reach `/admin/` on day one.
- `collectstatic` — CKEditor's toolbar/assets are static files; without this
  the editor and some images 404 in production.
- `check_email` — proves SMTP credentials and that a real message leaves the
  box. A broken mail server should be found here, not by a student waiting for
  a confirmation link.

`seed_demo` and `seed_match` are **development tools only**. `seed_demo` creates
fake students; `seed_match` also creates and approves a demo match, which sends
the real match notifications. Never run them against production data.

### Environment switches an admin cares about

| Variable | Default | Why the admin should care |
| --- | --- | --- |
| `DEBUG` | `True` | Must be `False` in production. Enables TLS redirect, secure cookies, HSTS. |
| `ALLOWED_HOSTS` | localhost | Production domain must be listed or every request 400s. |
| `SITE_URL` | `http://127.0.0.1:8000` | Used in emails, sitemap and canonical URLs. Set the real HTTPS domain. |
| `EMAIL_VERIFICATION_REQUIRED` | `False` | When `True`, unverified accounts are held on a notice page. |
| `MATCH_EMAILS_ENABLED` | `True` | Turns the "it's mutual" email on/off. In-app notifications still work. |
| `RATELIMIT_ENABLE` | `True` | Protects register/login/reset/crush actions from abuse. |
| `CACHE_BACKEND` | `locmem` | Multi-worker production should use `redis` so limits are shared. |
| `MINIMUM_AGE` | `18` | Age gate during identity creation. |
| `CONTACT_EMAIL` | `DEFAULT_FROM_EMAIL` | Where the public contact form is delivered. |

Full production checklist: `docs/deployment.md`.

---

## 3. The two ways to approve a match

Both paths call the same service function, so the data and notifications are
identical. The difference is the audit note.

| Path | Best for | Notes |
| --- | --- | --- |
| `/staff/matches/<id>/` | Every normal decision | Side-by-side identity comparison, review note field, single approve/reject. **Use this.** |
| `/admin/campus/potentialmatch/` | Bulk cleanup / emergencies | Approve/reject actions work on many rows at once and **cannot collect a note**. |

Approving from the admin list executes immediately. If you select the wrong
rows, real students are notified before you can fix it. Prefer the review desk,
and if you must use bulk actions, select rows one pair at a time and re-check
the selection before confirming.

---

## 4. Daily routine (15-30 minutes)

Do this every day, including weekends if the site is live. The queue is the
product; a stale queue means mutual crushes are sitting unseen.

### 4.1 Clear the pending match queue

**When:** at least once a day, and before any marketing push or campus event.

**Why:** a pending pair is *not* a match yet. Neither student is told anything
until you approve. Delay = the core feature appears broken.

**Steps**

1. Open `/staff/matches/`.
2. Work top to bottom (highest confidence first).
3. Click **Review** on one pair.
4. Verify the two identities (checklist below).
5. Add a short **Review note** explaining the decision.
6. Click **Approve match** only if certain. Otherwise **Reject match**.
7. Never approve a pair you have not opened and compared.

### 4.2 Verification checklist

Approve only when every line is true:

- [ ] Both students are at the **same college**.
- [ ] Both typed the same **normalized roll number** as the registered student
      (case, spaces and punctuation do not matter; different characters do).
- [ ] The typed **name** is the same person: allow spelling drift, but not a
      different surname or a different first name.
- [ ] **Course, year and section** do not contradict each other. A hard
      contradiction means two different people who happen to share a roll.
- [ ] It is a **reciprocal pair**: Person A entered Person B *and* Person B
      entered Person A. One-sided entries cannot be approved.
- [ ] Neither student is the other's own profile (self-match).
- [ ] There is no duplicate profile or duplicate campus involved.
- [ ] No block exists between the two students.

If anything is ambiguous, read the profiles, compare the matcher reasons, and
if still unsure: **reject with a note**. A missed match can be re-proposed
later; a wrong match cannot be un-announced.

### 4.3 What approval and rejection actually do

Approving:

- Creates one `MutualMatch` for the pair (or reuses an existing one).
- Marks **both** proposal halves `approved` and records `verified_by`,
  `verified_at` and your note.
- Sends exactly one in-app notification and one email to each student, and only
  if this approval is what created the match. Re-approval never re-notifies.
- Does **not** reveal names yet. Reveal needs both students to consent.

Rejecting:

- Marks both proposal halves `rejected` with your note.
- Sends nothing to either student.
- Permanently closes the pair; the matcher will not re-create it.

### 4.4 The unpaired list

`/staff/matches/` also shows one-sided entries under **One-sided entries**.
They are informational only: the other person has not entered them back, so
there is nothing to approve. Do not try to force them. They become a real pair
only when the other student seals a reciprocal entry.

### 4.5 Reports queue

**When:** daily; immediately for harassment or a safety report.

**Why:** reports are the only student-facing safety channel, and the public
site promises they are reviewed.

1. Open `/admin/campus/report/?status__exact=open`.
2. Read `reason` and `detail`. Treat the reporter's identity as confidential.
3. Open the reported student's profile and recent activity.
4. Decide:
   - Wrong person / typo: correct the offending entry or mark it inactive if
     appropriate.
   - Fake or impersonating profile: deactivate the underlying `User`
     (`/admin/auth/user/`), do not delete history unless policy requires it.
   - Harassment or inappropriate content: deactivate the account; add a
     `Block` if needed; preserve evidence.
   - Duplicate campus identity: deactivate the duplicate profile, keep the
     verified one.
   - Not a violation: dismiss.
5. Use **Mark reviewed** or **Dismiss** so the queue reflects the decision.
6. If you took an account action, note what and why somewhere the team keeps
   incident records.

The admin `Block` form only inserts a row. It does **not** run the cleanup the
in-product block button runs (retiring entries, deleting pending proposals,
closing matches). Prefer the student-facing block flow. If you must add a block
in admin, also clean the related `PotentialMatch` / `MutualMatch` rows manually.

### 4.6 Email verification requests

**When:** when a student says "I never got the link", or before enabling
`EMAIL_VERIFICATION_REQUIRED`.

**Why:** this flag controls *account email* confirmation, which affects login
and match-alert deliverability.

1. Ask the student to use **Resend verification** on the banner first.
2. Check `/admin/accounts/emailverification/` and search their email/username.
3. Confirm you are talking to the account owner (reply to the account email).
4. Select the row and run **Mark selected emails verified**, or open the row and
   set `verified_at`.

Do not confuse the two verification concepts:

| Field | Means | Effect |
| --- | --- | --- |
| `EmailVerification.verified_at` | The account's email address was confirmed | Removes the banner; matters when email verification is enforced |
| `StudentProfile.is_verified` | Editorial trust badge on the campus identity | Display/review aid only; it does not currently gate matching |

### 4.7 Contact inbox

The public contact form is delivered to `CONTACT_EMAIL`, not to `/admin/`.
Check that inbox daily. Reply from the same address, never from a personal one,
and never include another student's information.

---

## 5. Weekly routine

### 5.1 Review new student identities

**When:** once a week, or when the campus is growing quickly.

**Why:** campus + roll number is the identity gate. Bad identities create bad
matches.

In `/admin/campus/studentprofile/`:

- Filter by `is_verified = No`, `college`, and recent signups.
- Check roll format against the campus convention, duplicate-looking names and
  obviously fake profiles.
- Set `is_verified` only after you are confident. It is a badge, not a lock.
- Never edit a roll number to "fix" a match. A roll change can silently
  invalidate existing entries and proposals.
- If two profiles claim the same person, deactivate the duplicate account;
  never merge by deleting history blindly.

### 5.2 Campus hygiene

In `/admin/campus/college/`:

- There is no separate campus-approval queue. Decide duplicates deliberately
  with `is_active`.
- Keep one canonical row per real campus. Duplicates split the matching pool.
- `is_active = False` hides the campus from the picker and its landing page
  404s, but existing students keep working. Use this instead of deleting.
- Do not change `slug` after the campus has been shared: `/college/<slug>/` and
  `/join/<slug>/` links will break.
- Deletion is protected while profiles/entries reference the campus. Deactivate
  rather than delete unless you are certain.

### 5.3 College invite queue

`/admin/campus/collegeinvite/` records "please add/nudge my campus" requests.
The status field is a tracking tool only; changing it sends no email.

- `pending` — not acted on.
- `approved` — campus exists or was added.
- `declined` — cannot/should not add it.

Clear the queue weekly so growth decisions are based on real demand.

### 5.4 Pro Tips review

In `/admin/blog/post/`:

- Check the publishing calendar: drafts, future-dated posts and scheduled
  posts. A future `published_at` stays hidden until that time.
- Keep the **Featured** set small and genuinely useful (the launch content uses
  three).
- Proofread title, excerpt, cover image and category.
- Verify links and inline images still load.
- Unpublish anything outdated or inaccurate instead of deleting it, unless
  there is a legal reason to remove it.

### 5.5 Backups and deliverability

- Confirm the database and `MEDIA_ROOT` backups ran and are recent.
- Run `python manage.py check_email --to you@example.com` after any mail or
  hosting change, and spot-check once a week.
- Watch the `config.mail` log line for delivery failures. In-app notifications
  are written even when email fails, so a silent mail outage is easy to miss.
- Run `python manage.py check` after configuration changes.

---

## 6. Monthly and quarterly routine

### Monthly

- **Re-run the matcher** after imports, bulk profile edits, or a suspected
  missed pair:
  ```powershell
  python manage.py shell -c "from campus.services import reconcile_all_matches; print(reconcile_all_matches())"
  ```
  This only queues proposals. It never approves or notifies anyone.
- **Prune broken matches** only after a backup, and only if you know why they
  are broken:
  ```powershell
  python manage.py shell -c "from campus.services import prune_broken_matches; print(prune_broken_matches())"
  ```
  This deletes `MutualMatch` rows that have no approved proposal and a rejected
  reciprocal proposal. It does not delete notifications.
- Review staff accounts: remove access from people who no longer need it.
  Deactivate, do not delete, so the audit trail survives.
- Run the test suite: `python manage.py test`.
- Check `/sitemap.xml` and `/robots.txt` return 200 and use the real domain.
- Skim the growth numbers: active students per campus, matches per campus per
  week, reveal consent rate, reports backlog. Aggregate counts only; never
  surveil an individual student.

### Quarterly

- Restore a backup into a staging environment and verify it works. An untested
  backup is a guess.
- Rotate secrets that may have been exposed; rotate the `SECRET_KEY` only with
  the understanding that it logs every session out.
- Update dependencies in a staging environment, then deploy.
- Audit content for stale claims, broken links and outdated screenshots.

---

## 7. Model-by-model admin reference

### College (`/admin/campus/college/`)

| | |
| --- | --- |
| **When** | A new campus must be added, a duplicate cleaned up, or a campus should stop appearing. |
| **Why** | Campus is the hard boundary. Cross-campus matching is never allowed. |
| **Do** | Keep name/city/state accurate, leave `slug` alone after sharing, set `is_active` instead of deleting. |
| **Don't** | Merge two real campuses because they look similar. Do not delete a campus with history. |

### StudentProfile (`/admin/campus/studentprofile/`)

| | |
| --- | --- |
| **When** | Weekly verification, a report investigation, or a duplicate. |
| **Why** | This is the only identity the matcher trusts, combined with the roll number. |
| **Do** | Verify against the campus convention; deactivate the underlying user for fakes. |
| **Don't** | Edit roll numbers/names to "make a match work". Do not assume `is_verified` blocks matching; it does not. |

`is_verified` is editable directly in the list, which is convenient for bulk
review. Make sure the list is filtered correctly before saving.

### CrushEntry (`/admin/campus/crushentry/`)

| | |
| --- | --- |
| **When** | Debugging a specific match, handling a wrong-person report, or auditing a proposal. |
| **Why** | It stores what a student typed by hand, including the internal priority. |
| **Do** | Read the minimum needed. Mark `is_active` false only when the student asks or a report requires it. |
| **Don't** | Expose, screenshot, copy or discuss `priority`. Never change `priority` casually (it is unique per student). Never edit someone's entry to force a match. |

Priority is 1-3 and must never appear in a student-facing template, email,
notification or support reply. The review desk shows it to the verifier only
because the verifier is checking the submission.

### PotentialMatch (`/admin/campus/potentialmatch/`)

| | |
| --- | --- |
| **When** | This is the review queue. |
| **Why** | It is the only path from "someone typed a name" to an announced match. |
| **Do** | Use `/staff/matches/<id>/`, or the Approve/Reject actions if you must. Record notes. |
| **Don't** | Change `status`, `verified_by` or `mutual_match` by hand. Do not approve unpaired rows. Do not bulk-approve without checking every pair. |

The confidence score is advisory. It is built from name similarity (40), course
(20), year (15), section (10), department (8) and nickname (7); the identity
gate is always campus + normalized roll. A high score is not proof; a hard
course/year/section contradiction disqualifies a pair outright.

### MutualMatch (`/admin/campus/mutualmatch/`)

| | |
| --- | --- |
| **When** | Closing a match after a report/block, or auditing an approved match. |
| **Why** | Matching is sensitive; closure must be deliberate. |
| **Do** | Use **Close selected matches** for a clean closure. It changes status only and notifies nobody. |
| **Don't** | Set `status = revealed` by hand; that bypasses the two-sided consent flow. Do not delete a match row to "undo" an approval; close it and record the reason. |

Statuses: `mutual` (approved, nobody has chosen reveal), `reveal_pending` (one
side chose reveal), `revealed` (both consented), `closed`. `user_a_consented`
and `user_b_consented` belong to the students, not the admin.

### Report (`/admin/campus/report/`)

| | |
| --- | --- |
| **When** | Daily. |
| **Why** | Safety and trust; the site promises reports are reviewed. |
| **Do** | Investigate, take account action when warranted, then mark reviewed or dismissed. |
| **Don't** | Reveal the reporter to the reported student. Do not dismiss without reading. |

### Block (`/admin/campus/block/`)

| | |
| --- | --- |
| **When** | A student requests it outside the normal flow, or as part of an investigation. |
| **Why** | Blocking severs matching between two identities. |
| **Do** | Prefer the student-facing block action, which also cleans entries, proposals and matches. |
| **Don't** | Treat an admin-created row as complete: the admin form does no cleanup. |

### CollegeInvite (`/admin/campus/collegeinvite/`)

| | |
| --- | --- |
| **When** | Weekly queue review. |
| **Why** | It shows real demand for missing campuses. |
| **Do** | Set `approved` once the campus exists, `declined` when it will not be added. |
| **Don't** | Expect changing status to email anyone; it does not. |

### Notification (`/admin/campus/notification/`)

| | |
| --- | --- |
| **When** | Debugging "I got an alert" or correcting a bad send. |
| **Why** | Notifications must stay vague; a leak here exposes the whole secret. |
| **Do** | Keep messages generic ("Someone you secretly selected also selected you."). |
| **Don't** | Edit a message to include a name, roll number, priority or list position. |

### Rose (`/admin/campus/rose/`)

Existing in the data model, **dormant in the product**: there is no purchase
flow, no gateway and no refund process. Do not promise roses to students or
mark payments as paid manually. Leave rows untouched until a real payment story
is shipped.

### EmailVerification (`/admin/accounts/emailverification/`)

| | |
| --- | --- |
| **When** | "The link never arrived" / verification support. |
| **Why** | It controls account email confirmation, not campus identity. |
| **Do** | Ask the student to resend first; manually verify only after ownership is confirmed. |
| **Don't** | Mark a whole list verified to clear a queue. |

### Category and Post (`/admin/blog/category/`, `/admin/blog/post/`)

See the Pro Tips workflow below.

### User and Group (`/admin/auth/user/`, `/admin/auth/group/`)

| | |
| --- | --- |
| **When** | Staff onboarding/offboarding, fake account deactivation. |
| **Why** | Access control and the audit trail. |
| **Do** | Deactivate (`is_active = False`) instead of deleting staff. Use groups for repeatable permissions. |
| **Don't** | Grant superuser for convenience. Never edit a user's password on their behalf without a reset. |

---

## 8. Pro Tips workflow

### Create a category

`/admin/blog/category/add/`

- `name` — short, public-facing.
- `slug` — auto-filled from the name; changing it breaks existing archives.
- `description` — one line shown above the archive.
- `accent` — yellow, pink, blue, green or red.
- `order` — lower appears first; editable in the list.

### Create or edit a post

`/admin/blog/post/add/`

1. **Title** — clear, specific, no clickbait.
2. **Slug** — auto-filled; keep it stable once published.
3. **Category** — required for a good archive; may be empty, but avoid it.
4. **Author name** — defaults to WhoIsMyCrush; use a real byline only with
   consent.
5. **Excerpt** — one or two sentences, max 320 characters. This is the index
   and search result text.
6. **Cover image** — optional, JPG/PNG/WEBP/GIF, max 5 MB. It is converted to
   WebP automatically and the old file is removed.
7. **Body** — CKEditor rich text. The public site sanitizes it at render time,
   so scripts/iframes/event handlers are stripped. Do not rely on raw HTML.
8. **Featured** — only for genuinely important guides; keep the set small.
9. **Publishing** — tick `is_published`. If `published_at` is empty it is set
   to now; set it in the future to schedule. The server runs in UTC, so convert
   your local time before scheduling.
10. **SEO** — `seo_title`, `meta_description`, `canonical_url`. Leave canonical
    empty unless this content is a duplicate of another URL.
11. **Save**, then open the public post and check it on desktop and mobile.

Inline images use the same staff-only upload endpoint and the same 5 MB/type
limits. If the editor toolbar or uploads 404 after deploy, run
`collectstatic`.

### Publishing checklist

- [ ] Title and excerpt read naturally.
- [ ] Cover is the right aspect ratio and under 5 MB.
- [ ] Headings use the editor's heading styles (h2/h3), not bold paragraphs.
- [ ] Links open the intended page.
- [ ] No private student information, screenshots or real names.
- [ ] SEO title and description are written, not left as accidental defaults.
- [ ] Post is in the right category.
- [ ] Previewed on mobile.
- [ ] `is_published` and `published_at` are correct.

To take a post down, untick `is_published` and save. This keeps the row and
slug so it can be republished later; the public URL returns 404 while it is
unpublished. Delete only for legal or security reasons.

---

## 9. Email and notification rules

What the system sends:

| Trigger | Recipient | Channel | Content |
| --- | --- | --- | --- |
| Account sign-up / resend | Account email | Email | Confirmation link |
| Match approved | Both students | In-app + email (if enabled) | "Someone you secretly selected also selected you." |
| Reveal chosen by one side | The other side | In-app | "Your mutual crush chose to reveal. Open to finish." |
| Report / block | Nobody | None automatic | Admin acts manually through the report queue |
| Contact form | `CONTACT_EMAIL` | Email | Name/email/message |

Non-negotiable rules:

- Never add a name, roll number, priority, list position or "who liked first"
  to a notification or email.
- Never email a student to say they were entered as a crush. That is the exact
  secret the product protects.
- A match email is sent only from the approval service, only once per pair, and
  only while `MATCH_EMAILS_ENABLED` is on. The in-app notification is always
  written, so a mail outage never hides a match.
- Do not send a manual "congratulations" email. Use the product flow.

If students report missing emails, run `check_email` before changing anything.
For Gmail, `EMAIL_HOST_PASSWORD` must be an app password, not the account
password.

---

## 10. Maintenance commands

Run from the project root with the virtual environment active.

| Command | When | Why | Safe to repeat? |
| --- | --- | --- | --- |
| `python manage.py migrate` | Every deploy | Apply schema changes | Yes |
| `python manage.py collectstatic --noinput` | Every deploy / CKEditor update | Serve admin, editor and site assets | Yes |
| `python manage.py seed_posts` | Fresh install, content refresh | Launch Pro Tips | Yes, updates by slug |
| `python manage.py seed_colleges` | Fresh install | Starter campus list | Yes |
| `python manage.py seed_colleges --flush` | Only on a throwaway DB | Remove non-starter campuses | **No**; fails while referenced |
| `python manage.py seed_demo` | Development only | Fake students for clicking through | **No** on production |
| `python manage.py seed_match` | Development only | Creates and approves a demo match | **No** on production |
| `python manage.py check_email --to you@x.com` | After mail changes, weekly | Prove SMTP works end to end | Yes |
| `python manage.py check` | After config changes | Catch configuration errors | Yes |
| `python manage.py test` | Before deploy, monthly | Regression safety net | Yes |
| `python manage.py createsuperuser` | Once per environment | Owner access | Only when needed |
| `python manage.py shell -c "from campus.services import reconcile_all_matches; print(reconcile_all_matches())"` | After imports / suspected misses | Re-queue proposals, never approves | Yes |
| `python manage.py shell -c "from campus.services import prune_broken_matches; print(prune_broken_matches())"` | Rarely, after backup | Delete provably broken match rows | Careful |

Always take a database backup before shell snippets or bulk admin edits.

---

## 11. Incident playbook

### A wrong match was approved

The email/notification cannot be un-sent, so act quickly and consistently:

1. Open the `MutualMatch` and set it to `closed` (or use **Close selected
   matches**). This stops the reveal flow and removes it from open matches.
2. If the approval was clearly erroneous, correct or add a note on the related
   `PotentialMatch` rows so the audit trail explains what happened. Do not wipe
   the original note.
3. Record who approved it, when, and why it was wrong. Do not delete history.
4. Contact the affected students using `CONTACT_EMAIL` with a short, factual
   apology. Never repeat private list details in the message.
5. If the cause was a duplicate profile, fix the duplicate before the same pair
   can be proposed again.

### A duplicate student or campus appears

- Student: identify the real profile, deactivate the duplicate user, keep the
  verified one. Do not force the duplicate's entries onto the real profile.
- Campus: set the duplicate `is_active = False`; do not delete while it has
  history. Add a note for the team.

### Spam or abuse wave

1. Check the reports queue and the offending accounts.
2. Deactivate the accounts.
3. Verify rate limiting is on (`RATELIMIT_ENABLE=True`) and, in multi-worker
   production, that Redis/Memcached is actually reachable.
4. If a specific campus is targeted, deactivate the offending accounts first.
   Setting the campus `is_active = False` only blocks new joins and hides its
   landing page; existing students keep working, so it is not a substitute for
   account-level action.

### Email outage

1. Run `python manage.py check_email --to you@example.com`.
2. Confirm `EMAIL_BACKEND` is SMTP in production (the default console backend
   writes mail to the terminal only).
3. Check app-password/credential expiry.
4. Inspect the `config.mail` logger output.
5. Remember: in-app match notifications still exist, so students are not
   completely blind during the outage.

### Queue is empty but a mutual match is expected

- Confirm both students actually sealed reciprocal entries.
- Check that neither side blocked the other.
- Check that the roll numbers normalize to the same value and that course/year/
  section do not contradict.
- Run the reconcile command; it only queues proposals.
- Inspect the `PotentialMatch` rows for the pair: a previously rejected row
  will not be recreated.

### Data loss or security incident

1. Stop writes / take the service down if confidentiality is at risk.
2. Restore the most recent verified backup into staging first.
3. Rotate `SECRET_KEY`, database credentials and email credentials as
   appropriate. Rotating `SECRET_KEY` logs everyone out.
4. Review staff accounts and recent `verified_by` activity.
5. Preserve logs; do not destroy evidence.

---

## 12. Do and do not

**Do**

- Use your own named admin account.
- Open and compare every pair before approving.
- Write a short review note for every decision.
- Prefer `/staff/matches/` over bulk admin actions.
- Keep notifications vague and free of private data.
- Use `is_active` instead of deletion for users, campuses and staff.
- Take a backup before any shell command or large edit.
- Report aggregate numbers, never individual student activity.

**Do not**

- Reveal, screenshot, export or discuss anyone's crush entries or priority.
- Approve by name alone. Campus + roll is the identity gate.
- Approve a one-sided entry, a self-match, a cross-campus pair, or a blocked
  pair.
- Bulk-approve rows you have not individually reviewed.
- Set `MutualMatch.status = revealed` manually.
- Edit `PotentialMatch.status` manually instead of using approve/reject.
- Add match data to emails, notifications, blog posts or support replies.
- Delete staff users, because it erases the approval audit trail.
- Promise roses, payments or features that are not live.
- Run `seed_demo`, `seed_match` or `seed_colleges --flush` on production.

---

## 13. Cadence summary

| Cadence | Tasks |
| --- | --- |
| Every day | Pending match queue, open reports, contact inbox, email verification requests |
| Every week | New student identities, campus hygiene, college invites, Pro Tips review, backup + mail check, `manage.py check` |
| Every month | Reconcile, prune if needed, staff access review, test suite, sitemap/robots check, growth numbers |
| Every quarter | Restore-drill, secret rotation, dependency update, content audit |

---

## 14. Quick URL reference

| URL | Purpose |
| --- | --- |
| `/admin/` | Django admin |
| `/admin/campus/potentialmatch/` | Raw match proposal queue |
| `/staff/matches/` | Verification desk (preferred) |
| `/staff/matches/<id>/` | Side-by-side review + notes |
| `/admin/campus/report/` | Reports / moderation |
| `/admin/campus/studentprofile/` | Campus identities |
| `/admin/campus/college/` | Campuses |
| `/admin/campus/mutualmatch/` | Approved matches |
| `/admin/campus/collegeinvite/` | Campus invite demand |
| `/admin/accounts/emailverification/` | Account email status |
| `/admin/blog/post/` | Pro Tips posts |
| `/admin/blog/category/` | Pro Tips categories |
| `/admin/auth/user/` | Users, staff, permissions |
| `/pro-tips/` | Public Pro Tips |
| `/sitemap.xml`, `/robots.txt` | SEO health check |
