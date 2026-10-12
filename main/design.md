# WhoIsMyCrush.com

> **You might be someone's crush too.**

A private, anonymous mutual-crush platform designed specifically for college students.

The product should NOT feel like a dating app.

It should feel like a **secret college game** where students quietly submit the names of up to three people they like and wait to discover whether the feeling is mutual.

---

# 1. Product Vision

## Core idea

A college student can secretly select up to 3 people they have a crush on.

If any selected person has also selected them, the system creates a **Mutual Crush**.

Neither person should ever know:

* who selected them first
* what priority they had
* what priority they gave the other person
* whether they were #1, #2, or #3
* who else was selected

Priority is strictly internal.

The user only learns:

> ❤️ It's Mutual!

Identity reveal happens only through the defined reveal flow.

---

# 2. Target Audience

Initial MVP:

**College students in India**

Primary age group:

**18–25**

The product should feel:

* youthful
* playful
* secretive
* slightly mysterious
* college-specific
* fun
* private
* easy to understand

It should NOT feel:

* corporate
* like LinkedIn
* like Tinder
* like Bumble
* like a matrimonial website
* overly romantic
* childish
* visually cluttered

---

# 3. Brand Personality

WhoIsMyCrush should feel like:

> "A secret thing happening inside your college."

Imagine:

* college notice boards
* handwritten notes
* ID cards
* roll numbers
* classroom benches
* library slips
* hostel notice boards
* secret notes passed in class
* college canteen conversations
* scribbled names on notebooks

But transform those ideas into a modern Gen-Z interface.

---

# 4. Visual Direction

## Main visual concept

### "SECRET CAMPUS BOARD"

The interface should look like a modern digital version of a college notice board.

Use:

* off-white paper backgrounds
* black typography
* small sticker-like UI elements
* thin borders
* handwritten accents
* subtle paper texture
* index-card components
* notebook/grid patterns
* red stamp elements
* tiny campus-style labels
* playful micro-interactions

Avoid:

* gradients everywhere
* glassmorphism
* neon cyberpunk
* hearts floating everywhere
* giant romantic photographs
* typical dating-card swiping UI
* Tinder-style profile cards

---

# 5. Color System

Primary background:

```text
#F7F6F1
```

Ink:

```text
#111111
```

Soft red:

```text
#FF5C5C
```

Crush pink:

```text
#FFB6C1
```

Electric yellow:

```text
#FFF05A
```

Soft blue:

```text
#BFD7FF
```

Success green:

```text
#6EE7B7
```

Paper white:

```text
#FFFFFF
```

Use black and off-white as the dominant colors.

Accent colors should appear as small stickers, highlights and states.

---

# 6. Typography

Primary font:

**Manrope**

Use it for:

* headings
* body
* forms
* buttons
* navigation

Optional handwritten accent font:

**Caveat**

Use extremely sparingly.

Example:

```text
WHO IS YOUR CRUSH?

psst... nobody will know 👀
```

Do not use handwritten fonts for the entire interface.

---

# 7. Logo

Wordmark:

```text
whoismycrush
```

Possible treatment:

```text
whoismy
CRUSH?
```

The logo should look more like a secret note than a dating brand.

Small visual element:

```text
[ ? ]
```

or

```text
♥ ?
```

Avoid using a large traditional heart logo.

---

# 8. Homepage

## Hero

Large heading:

> # Who is your crush?

Small supporting text:

> You might be someone's crush too.

Description:

> Secretly pick up to 3 people from your college.
> We'll only tell you when it's mutual.

Primary CTA:

```text
[ Find Out ]
```

Secondary:

```text
How it works ↓
```

---

# 9. Homepage Visual

Hero should look like a physical college desk.

Example composition:

```text
┌─────────────────────────────────────┐
│                                     │
│       WHO IS YOUR CRUSH?            │
│                                     │
│     You might be someone's          │
│          crush too.                 │
│                                     │
│        [ Find Out ]                 │
│                                     │
│   ┌───────────────────────────┐     │
│   │ SECRET CAMPUS NOTE        │     │
│   │                           │     │
│   │  Pick up to 3 people.     │     │
│   │  Nobody will know.        │     │
│   │                           │     │
│   │        ???                │     │
│   └───────────────────────────┘     │
│                                     │
└─────────────────────────────────────┘
```

Use subtle rotation on some cards.

---

# 10. Homepage Trust Message

Immediately below hero:

```text
PRIVATE BY DESIGN

Your crush list stays hidden.

Nobody can see:
✓ who you selected
✓ your priorities
✓ who else you selected

We'll only tell you when it's mutual.
```

This is one of the most important sections.

---

# 11. How It Works

Three steps.

### 01 — Pick

> Pick up to 3 people from your college.

Visual:

A small college ID card.

---

### 02 — Wait

> They won't know you picked them.

Visual:

A sealed envelope.

---

### 03 — Match

> If they picked you too...

Visual:

Two sealed envelopes connecting.

Then:

> ❤️ It's Mutual.

---

# 12. Registration

Do NOT call it:

> Create Dating Profile

Instead:

> **Create your secret profile**

Small text:

> Just enough information to find the right person.

---

# 13. Registration Fields

Required:

```text
Full Name
College
Course
Year
Roll Number
Gender
Date of Birth / Age confirmation
Email
Password
```

Optional:

```text
Section
Profile nickname
```

---

# 14. College Selection

Page:

> **Which campus are you from?**

Search:

```text
[ Search your college... ]
```

Result:

```text
ABC College
Patna

XYZ University
Delhi

DEF College
Kanpur
```

After selection:

```text
✓ ABC College

Your crushes will only be searched within your college.
```

---

# 15. Student Identity

After college selection:

```text
FULL NAME

[ Aman Kumar ]

ROLL NUMBER

[ 23BCA104 ]

COURSE

[ BCA ▼ ]

YEAR

[ 2nd Year ▼ ]

SECTION

[ A ▼ ]
```

Important:

Roll number is primarily used for identity matching and verification.

Do not publicly display the complete roll number.

---

# 16. Crush Selection

Heading:

> **Okay... who do you secretly like?**

Subtext:

> Pick up to 3 people from your college.

Search:

```text
[ 🔎 Search by name or roll number ]
```

Example:

User types:

```text
niki
```

Search results:

```text
┌──────────────────────────────┐
│ Nikita Sharma                │
│ BCA · 2nd Year               │
│ Roll: •••27                  │
│                              │
│              [ Select ]      │
└──────────────────────────────┘
```

Do not show complete roll number.

---

# 17. Roll Number Matching

The user must provide their own roll number.

When selecting a crush, collect:

```text
Crush Name
Crush Roll Number
```

The system should use:

```text
college_id
roll_number
```

as the strongest identity combination.

Example:

```text
College:
ABC College

Crush:
Nikita Sharma

Roll Number:
27
```

Internally resolve this to:

```text
user_id = 184
```

The actual CrushSelection should store:

```text
from_user_id
to_user_id
priority
```

Never use the typed name as the final identity key.

---

# 18. Handling Spelling Mistakes

Names should NOT be the final matching mechanism.

Search should support:

```text
Niki
Nikki
Nikita
Nikhita
```

and:

```text
Riya
Ria
Rhea
```

Use normalized + fuzzy search to show possible candidates.

But final selection must resolve to an actual registered student.

The relationship is:

```text
User A → User ID 184
```

not:

```text
User A → "Nikki"
```

---

# 19. Unknown / Unregistered Crush

If the student cannot be found:

```text
Can't find them?

[ Invite your college ]
```

Do NOT allow arbitrary text to become a crush record.

This prevents false matches caused by:

* spelling mistakes
* duplicate names
* fake names
* wrong students

---

# 20. Three Crush Slots

The interface should feel playful.

```text
YOUR SECRET 3

┌─────────────────────┐
│ #01                 │
│                     │
│  Add someone...     │
│                     │
└─────────────────────┘

┌─────────────────────┐
│ #02                 │
│                     │
│  Add someone...     │
│                     │
└─────────────────────┘

┌─────────────────────┐
│ #03                 │
│                     │
│  Add someone...     │
│                     │
└─────────────────────┘
```

Do not visually emphasize #1 as "most important".

The numbers are only part of the private submission flow.

---

# 21. Priority Privacy Rule

Priority must NEVER be revealed.

Never display:

```text
You were their #1
You were their #2
You were their #3
```

Never display:

```text
Your crush ranked you second.
```

Never display priority in notifications.

Never expose priority through frontend API responses.

Priority is only stored for:

* internal matching data
* rose/business logic
* analytics

---

# 22. Submission Confirmation

After selecting up to 3 people:

```text
YOUR SECRET IS LOCKED 🔒

3 people selected.

Nobody can see your list.

[ Lock My Crushes ]
```

Confirmation animation:

A paper card slides into a digital envelope.

Then:

```text
SEALED.

Now we wait.
```

CTA:

```text
[ Go to my dashboard ]
```

---

# 23. Dashboard

Do NOT use a typical dating dashboard.

Instead:

### Secret Desk

```text
Good evening, Aman.

Your secret is safe here.

┌──────────────────────────┐
│                          │
│       🔒 SEALED          │
│                          │
│  Your crush list is      │
│  hidden.                 │
│                          │
│  Status: Waiting...      │
│                          │
└──────────────────────────┘
```

Below:

```text
CAMPUS STATUS

127 students from your college
have joined.

23 mutual crushes found.
```

Do not show identities.

---

# 24. Waiting State

Use mystery instead of a boring spinner.

Example:

```text
┌─────────────────────────┐
│                         │
│        ???              │
│                         │
│   Somewhere on campus   │
│   someone might be      │
│   thinking about you.   │
│                         │
│      WAITING...         │
│                         │
└─────────────────────────┘
```

Small rotating campus doodles can animate subtly.

---

# 25. Mutual Match

This is the biggest emotional moment.

Do NOT immediately show the person's name.

Screen:

```text
        WAIT.

          ↓

     IT'S MUTUAL.
```

Then:

```text
❤️

Someone you secretly selected
also secretly selected you.

Your secret stayed safe.

Their identity is still hidden.
```

CTA:

```text
[ Continue ]
```

---

# 26. Match Screen

```text
┌─────────────────────────────┐
│                             │
│          ❤️                │
│                             │
│       MUTUAL CRUSH          │
│                             │
│  You both chose each other. │
│                             │
│  Their identity is hidden.  │
│                             │
│   [ Reveal Together ]       │
│                             │
└─────────────────────────────┘
```

Important:

No priority information.

No ranking information.

No "they liked you more".

No comparison.

---

# 27. Reveal System

Identity should be revealed only according to the product's consent rules.

Example:

```text
REVEAL REQUEST

You can choose to reveal your identity
to your mutual crush.

[ Reveal ]
[ Keep Anonymous ]
```

If both sides agree:

```text
IT'S YOU.

❤️

Aman ↔ Priya
```

Then:

```text
You both secretly chose each other.
```

---

# 28. Rose System

Roses are optional digital gifts.

Do not frame them as payment for basic matching.

After a mutual match:

```text
SEND SOMETHING?

Make your secret match a little more special.
```

Options:

```text
🌹 Red Rose
₹100

🥈 Silver Rose
₹250

🏆 Golden Rose
₹500
```

Priority may internally determine which rose is associated with a match, but priority must never be revealed to either user.

---

# 29. Rose Delivery

Recipient sees:

```text
YOU GOT A ROSE 🌹

Someone from your mutual crush
sent you a rose.

The sender is still anonymous.
```

Optional message:

```text
"I've wanted to say this for a while."
```

Do not reveal identity automatically.

---

# 30. Payment

Payment flow:

```text
Select Rose
       ↓
Optional note
       ↓
Payment
       ↓
Success
       ↓
Rose delivered
```

Use a proper Indian payment provider such as Razorpay/Cashfree/UPI-compatible checkout during implementation.

Payment should never expose:

* sender's private priority
* crush list
* unrelated profile information

---

# 31. Navigation

Keep navigation extremely small.

Desktop:

```text
logo

How it works
My Secret
Matches
Profile

[ My Secret ]
```

Mobile:

```text
Logo          ☰
```

Bottom navigation can be:

```text
🏠 Home
🔒 Secret
❤️ Matches
👤 Me
```

Avoid 8–10 navigation items.

---

# 32. Profile Page

Call it:

> **My Campus ID**

Not:

> Dating Profile

Show:

```text
Aman Kumar

ABC College
BCA · 2nd Year

Roll No. •••104
```

Privacy controls:

```text
[ Hide my profile ]
[ Delete my crushes ]
[ Delete my account ]
```

---

# 33. Privacy Center

Important page:

> **Your secrets belong to you.**

Explain:

```text
Nobody can see your crush list.

Nobody can see your priorities.

Nobody can see who else you selected.

Your crush will not be notified just because
you selected them.

A match only happens when both sides select
each other.
```

Buttons:

```text
Delete all crush selections
Delete account
```

---

# 34. Anti-Abuse

The product must include:

* email verification
* phone verification where appropriate
* college verification
* one active identity per student
* rate limiting
* suspicious activity detection
* block user
* report user
* profile removal
* account deletion
* crush list deletion

Never allow:

* anonymous public comments
* anonymous public messages
* unlimited crush selections
* mass targeting
* public lists of crushes

---

# 35. College Boundary

For MVP:

A user can only select a crush from the same college/community.

Example:

```text
Aman
ABC College

Can select:
✓ ABC College students

Cannot select:
✗ XYZ College students
✗ Random internet users
```

This makes matching much more meaningful.

---

# 36. Matching Algorithm

The final relationship should be based on user IDs.

Example:

```text
Aman → Priya
Priya → Aman
```

If both exist:

```text
MATCH = TRUE
```

Priority is separate:

```text
Aman → Priya = 1
Priya → Aman = 2
```

The match remains:

```text
Mutual Crush
```

No priority information is returned to either user.

---

# 37. Data Model Concept

## College

```text
id
name
city
state
domain
is_active
created_at
```

## StudentProfile

```text
id
user
college
full_name
roll_number
course
year
section
gender
is_verified
is_searchable
created_at
```

Unique identity should be based on the appropriate college/student identifier.

For example:

```text
college + normalized_roll_number
```

where the college's roll-number system supports that reliably.

---

# 38. CrushSelection

```text
id
from_user
to_user
priority
created_at
is_active
```

Constraints:

```text
One user cannot select the same person twice.

Maximum 3 active selections per user.

from_user != to_user
```

---

# 39. MutualMatch

Can either be calculated dynamically or persisted.

Suggested:

```text
id
user_a
user_b
created_at
status
revealed_at
```

Status:

```text
MUTUAL
REVEAL_PENDING
REVEALED
CLOSED
```

---

# 40. Rose

```text
id
match
sender
receiver
rose_type
amount
message
payment_status
created_at
```

Rose types:

```text
RED
SILVER
GOLDEN
```

---

# 41. Design Language

UI components should look like physical college objects.

Use:

### Index cards

```text
┌────────────────────────┐
│ SECRET NOTE #07        │
│                        │
│ ?????                  │
└────────────────────────┘
```

### Stamps

```text
[ PRIVATE ]
[ SEALED ]
[ MUTUAL ]
[ VERIFIED ]
```

### Doodles

Small:

```text
✦
?
♡
→
...
```

Use them as decoration, not everywhere.

---

# 42. Microinteractions

Important interactions:

### Selecting a crush

Card slightly rotates and gets stamped:

```text
SELECTED ✓
```

### Sealing

Paper folds into envelope.

### Waiting

Tiny blinking:

```text
waiting...
```

### Mutual match

Screen briefly pauses before revealing:

```text
...
...
...

IT'S MUTUAL.
```

This creates anticipation.

---

# 43. Animation Rules

Animation should be:

* fast
* subtle
* playful

Use:

```text
150–300ms
```

for normal UI transitions.

Special match animation can be:

```text
600–1000ms
```

Avoid excessive animations.

The website should still feel fast on mobile networks.

---

# 44. Mobile First

Primary users will probably use mobile.

Design for:

```text
360px
390px
412px
```

first.

Desktop should be an adaptation.

Forms should be extremely easy to complete on a phone.

---

# 45. Landing Page Copy

Hero:

> # Who is your crush?

Subtitle:

> You might be someone's crush too.

Supporting:

> Pick up to 3 people from your college.
> Keep it secret. We'll only tell you when it's mutual.

CTA:

> **Find My Crush**

Privacy line:

> 🔒 Your secrets stay private.

---

# 46. Empty State

No matches:

> Still waiting...

```text
Maybe they're here.

Maybe they're thinking about you.

Maybe they haven't joined yet.
```

CTA:

```text
[ Invite Your College ]
```

---

# 47. Match Notification

Do NOT say:

> Priya likes you.

Instead:

> ❤️ **It's mutual.**

Body:

> Someone you secretly selected has secretly selected you too.

CTA:

> **See what happened**

---

# 48. Email / Notification Copy

Example:

```text
Subject:
Someone might be your mutual crush 👀

You selected someone.

They selected you too.

Your secret is still safe.

Open WhoIsMyCrush
```

Never put the crush's name in an email notification.

---

# 49. Error States

Example:

```text
Hmm...

We couldn't find a student with those details.

Check the college, name and roll number.
```

Never say:

```text
This person definitely doesn't exist.
```

because the account may simply be hidden/unregistered.

---

# 50. Security Principle

Never trust frontend data.

The backend must independently verify:

* college
* student identity
* crush ownership
* priority ownership
* match existence
* reveal permission
* payment status

Priority must never be accepted blindly from the frontend.

---

# 51. API Privacy

Bad:

```json
{
  "match": true,
  "their_priority": 2,
  "your_priority": 1,
  "selected_by": 184
}
```

Good:

```json
{
  "match": true,
  "status": "mutual"
}
```

Only return information necessary for the current screen.

---

# 52. What Makes WhoIsMyCrush Different

The product is NOT:

```text
Swipe
Like
Match
Chat
Date
```

Instead:

```text
SECRET
   ↓
SELECT
   ↓
WAIT
   ↓
MYSTERY
   ↓
MUTUAL
   ↓
REVEAL
```

The mystery is the product.

---

# 53. MVP Scope

## Version 1

Build only:

```text
Landing page
Registration
Login
College selection
Student profile
Roll number
Student search
Crush selection
Maximum 3 crushes
Priority storage
Mutual matching
Private match notification
Dashboard
Profile
Privacy controls
```

## Version 1.1

```text
Reveal system
Email notifications
Phone verification
College invite
Block/report
```

## Version 2

```text
Roses
Payments
Secret notes
Match animations
Campus statistics
College ambassador system
Referral system
```

---

# 54. Things NOT to Build in MVP

Do not build:

```text
Public feed
Followers
Likes
Comments
Chat
Stories
Swipe cards
Dating recommendations
AI matchmaking
Public profiles
Location tracking
Instagram integration
```

The simplicity is part of the product.

---

# 55. Core Product Loop

```text
Student joins college
        ↓
Creates private campus identity
        ↓
Selects up to 3 crushes
        ↓
Seals the list
        ↓
Waits
        ↓
Another student selects them
        ↓
Backend detects reciprocal selection
        ↓
MUTUAL CRUSH
        ↓
Both remain anonymous
        ↓
Optional reveal
        ↓
Optional rose
```

---

# 56. Final Brand Statement

## WhoIsMyCrush.com

### You might be someone's crush too.

> Pick up to 3 people from your college.
>
> Nobody will know.
>
> Unless they picked you too.

Primary CTA:

```text
[ Enter Your Campus ]
```

Secondary:

```text
How it works
```

---

# 57. Overall UI Rule

Every screen should make the user feel:

> **"I'm doing something secret."**

Not:

> "I'm using another dating app."

The visual language should combine:

**college identity + mystery + privacy + playful Gen-Z design**

with a clean modern interface.

The product's emotional progression should be:

**Curiosity → Secret → Suspense → Surprise → Mutuality**

That progression is more important than decorative romance.
