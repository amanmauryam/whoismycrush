# Growth plan

Growth is deliberately *campus-first*: a match only means something when a
college has two real students on it, so nothing here trades that for raw
signups.

## Live today

### College landing + join links (`campus`)

- Every `College` has a readable `slug` (migration `0003` backfills existing
  rows).
- `/college/<slug>/` — a public page with the college name, member count and a
  share card. **Not** a directory: no student list. `noindex` until 5+ members,
  never in the sitemap (`CollegeGrowthTests` lock this in).
- `/join/<slug>/` — the shareable invite link: preselects the campus in the
  session, then routes to register (anonymous), identity (new account) or the
  dashboard (existing student).
- The college landing has a copy-to-clipboard join link and an OG-ready card.

### Pro Tips (`blog`)

- Canonical home at `/pro-tips/`; old `/blog/` URLs permanently redirect.
- Manager-backed publishing: drafts and future-dated posts are never visible.
- CKEditor 5 authoring for staff, with validated inline images and covers.
- Categories, featured lead, search, pagination and related reading.
- Sanitized HTML bodies (`config.sanitize.sanitize_html`) - scripts and their
  contents are dropped, event handlers stripped, unsafe URL schemes refused.
- Per-post SEO fields, reading time, generated table of contents and
  `BlogPosting` JSON-LD.
- Launch content: `python manage.py seed_posts` (idempotent, 14 guides across
  six categories).

### FAQ (`/faq/`)

- Question groups in `config/content.py`, rendered as accessible
  `<details>` accordions, with matching `FAQPage` structured data.

### Campus picker growth

- "Add your college" lets the first student from a missing campus bootstrap it
  in seconds (case-insensitive de-dupe under a 10/h IP limit).

## Designed but intentionally not built

### Roses

`campus.Rose` exists in the data model and admin, the FAQ explains they are
optional and **not live**. There is deliberately no purchase flow: a paid
item that "unlocks" a match would corrode trust and the privacy story, so it
stays dormant until there is a real need and a payment/refund story.

### Persona-driven expansion

- Notifications/lifecycle emails must stay vague ("something changed") — never
  "your selection X".

## Next experiments (ranked)

1. **Referral density** — post-match prompt to invite *one* friend from the
   same campus, since every new member raises the expected value of the whole
   campus.
2. **Campus ambassadors** — students who share `/join/<slug>` links; measure
   by joined-per-link with the dashboard (no leaderboards of people).
3. **Match timing** — a short, honest "waiting" screen (already present) to
   keep the reveal special and discourage spam-sealing.
4. **Search lightbox** — on `/campus/`, highlight "your college might be
   under a slightly different name" to cut manual re-adds (de-dupe already
   exists).

## Metrics that matter

- Activated students per campus relative to campus size.
- Verified mutual matches per campus per week.
- Reveal consent rate (both-sides opt-in) and close rate.
- Join-link conversion (landing → registered student of that campus).
- Reports/accounts as a safety signal, tracked privately.

## Explicit non-goals

- No public leaderboards, follower counts, or "who liked you" feeds.
- No cross-campus matching.
- No buzzword growth loops that leak privacy guarantees.