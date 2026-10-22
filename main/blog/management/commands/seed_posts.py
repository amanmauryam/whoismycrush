"""Seed the public blog with the launch guides.

Idempotent: safe to run repeatedly. Posts are matched on slug and updated in
place, so editing this file and re-running refreshes the live copy without
creating duplicates.
"""

from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from blog.models import Category, Post

CATEGORIES = [
    {
        "slug": "account-guides",
        "name": "Account guides",
        "description": "Sign-up, profile and privacy settings without the guesswork.",
        "accent": "blue",
        "order": 1,
    },
    {
        "slug": "feature-tutorials",
        "name": "Feature tutorials",
        "description": "Campus picker, secret list, matches and the small buttons that matter.",
        "accent": "pink",
        "order": 2,
    },
    {
        "slug": "secret-tips",
        "name": "Secret tips",
        "description": "The unwritten rules of campus crushes, mutual matches and being brave-ish.",
        "accent": "yellow",
        "order": 3,
    },
    {
        "slug": "privacy",
        "name": "Privacy",
        "description": "What stays secret, what the site can see and how to lock things down.",
        "accent": "green",
        "order": 4,
    },
    {
        "slug": "troubleshooting",
        "name": "Troubleshooting",
        "description": "When a link, account or campus does not behave. Fix it here.",
        "accent": "red",
        "order": 5,
    },
    {
        "slug": "website-tricks",
        "name": "Website tricks",
        "description": "Tiny shortcuts and smart moves that make the site feel faster.",
        "accent": "blue",
        "order": 6,
    },
]

POST_CATEGORIES = {
    "why-your-secret-crush-feels-impossible-to-say-out-loud": "secret-tips",
    "what-is-a-secret-crush-really": "secret-tips",
    "how-to-tell-if-someone-likes-you-without-asking": "secret-tips",
    "the-case-for-keeping-your-crush-list-private": "privacy",
    "college-crush-culture-why-campus-only-matters": "secret-tips",
    "what-to-do-after-a-mutual-crush-match": "feature-tutorials",
    "secret-admirer-vs-secret-crush": "secret-tips",
    "is-it-weird-to-have-a-crush-on-a-classmate": "secret-tips",
    "how-to-handle-a-crush-you-cant-act-on": "secret-tips",
    "the-psychology-of-mutual-attraction": "secret-tips",
    "create-your-secret-profile-without-overthinking-it": "account-guides",
    "campus-picker-tutorial-find-or-add-your-college": "feature-tutorials",
    "cant-find-your-college-quick-troubleshooting": "troubleshooting",
    "5-small-website-tricks-that-make-whoismycrush-easier": "website-tricks",
}

FEATURED_POSTS = {
    "create-your-secret-profile-without-overthinking-it",
    "how-to-tell-if-someone-likes-you-without-asking",
    "the-case-for-keeping-your-crush-list-private",
}

# The later additions are launch content, so keep them near the top of the
# archive instead of letting the line number make them look months old.
NEW_POST_DAYS_AGO = {
    "create-your-secret-profile-without-overthinking-it": 2,
    "campus-picker-tutorial-find-or-add-your-college": 5,
    "cant-find-your-college-quick-troubleshooting": 8,
    "5-small-website-tricks-that-make-whoismycrush-easier": 11,
}

POSTS = [
    {
        "slug": "why-your-secret-crush-feels-impossible-to-say-out-loud",
        "title": "Why Your Secret Crush Feels Impossible to Say Out Loud",
        "excerpt": (
            "The maths of confessing is brutal: one small chance of a yes "
            "against a very real chance of awkwardness forever. Here is why "
            "silence wins so often — and a lower-stakes route."
        ),
        "body": """
<p>It is not that you are shy. It is that the deal on the table is genuinely
bad. You get one attempt, it happens in front of a real person, and the two
outcomes are not equal. A yes is lovely. A no is awkward every time you pass
each other for the rest of the term.</p>

<h2>The risk is permanent, the reward is not bigger</h2>
<p>When something feels expensive and irreversible, the sensible brain says
"wait". So you wait for a better moment, a clearer sign, a lower-stakes
setting. Often the year ends before the moment arrives.</p>

<h2>What silence is actually protecting</h2>
<ul>
  <li>Your dignity if the answer is no.</li>
  <li>The friendship, which you don't want to gamble.</li>
  <li>The ordinary ease of walking into the same room.</li>
</ul>
<p>Those are real things. Anyone who tells you to "just go for it" is not the
one who has to sit through the canteen afterwards.</p>

<h2>What silence costs</h2>
<p>The cost is quieter, which is exactly why we underrate it. It is the
"what if" that shows up at 2am, and the small, strange grief of never knowing.
Most crushes do not fade because the feeling was wrong. They fade because
nobody ever got a straight answer.</p>

<h2>A lower-stakes route</h2>
<p>What you want is the information without the confession. That is a
different problem, and it has a different solution: find out whether the
feeling is mutual without either of you having to say it first. On
WhoIsMyCrush, you add someone privately, and nothing is ever said to them
unless they added you too. No speech, no moment, no risk of a bad reaction —
just a yes that only appears when it is real.</p>
""",
    },
    {
        "slug": "what-is-a-secret-crush-really",
        "title": "What Is a Secret Crush, Really?",
        "excerpt": (
            "A crush is a feeling; a secret crush is a feeling plus one rule. "
            "That single rule changes how it works, what it means, and why it "
            "can still end well."
        ),
        "body": """
<p>The dictionary version is simple: a secret crush is someone you are
attracted to or fond of, that you have not told. The interesting part is not
the feeling. It is the rule you have wrapped around it.</p>

<h2>The one rule</h2>
<p>The rule is "they must not know". That rule is doing a lot of work. It
protects you from a bad answer, it protects them from an awkward one, and it
keeps the whole thing safely hypothetical. It also means the feeling can
grow for a long time without ever touching reality.</p>

<h2>A secret crush is not a plan</h2>
<p>It is easy to confuse the two. You can rehearse a confession for months
and still never intend to give it. That is fine — but be honest with yourself
about which one you are doing, because only one of them can end in an answer.</p>

<h2>Why "secret" and "mutual" are not opposites</h2>
<p>Here is the part people miss. Two people can have a secret crush on each
other at the same time, and neither finds out — because both are following
the same rule. The secret is not a property of the crush. It is a property of
the situation, and situations can change without anyone having to be brave.</p>

<blockquote>
  <p>The most common mutual crush is the one nobody mentions. Both people
  feel it, both people wait, and the term ends.</p>
</blockquote>

<h2>What changes when you know</h2>
<p>A secret crush becomes a fact the moment it turns out to be mutual. That
is a much better problem to have. The feeling did not change; the
<em>information</em> did. And information is what you were actually missing
the whole time.</p>
""",
    },
    {
        "slug": "how-to-tell-if-someone-likes-you-without-asking",
        "title": "How to Tell If Someone Likes You (Without Asking)",
        "excerpt": (
            "You cannot read minds, and nobody can. But there are honest, "
            "well-worn signals of interest — and one honest way to find out "
            "for certain."
        ),
        "body": """
<p>Let's be clear from the start: none of these are proof. People are varied,
shy, friendly, distracted and polite in different amounts. Treat signals as
hints, not verdicts.</p>

<h2>Signals that are worth noticing</h2>
<ul>
  <li><strong>They start things.</strong> A message with no practical reason
    behind it is a strong signal. Initiative is costly, and people spend it
    on people they are curious about.</li>
  <li><strong>They linger.</strong> Conversations that outlast their subject.
    Goodbyes that take three tries.</li>
  <li><strong>They remember small things.</strong> The deadline you mentioned
    once, the drink you don't like. Attention is a form of care.</li>
  <li><strong>They mirror you.</strong> Posture, phrasing, pace. This is
    mostly automatic and mostly unconscious.</li>
  <li><strong>They get a little nervous.</strong> Not always, but a
    confident person who suddenly can't finish a sentence around you is
    telling you something.</li>
</ul>

<h2>The honest problem with signals</h2>
<p>Every one of these has an innocent explanation. "They're just friendly."
"They're like that with everyone." You can spend a whole year collecting
evidence that never adds up to an answer, because the signals were never
built to be decisive.</p>

<h2>When no signal is itself a signal</h2>
<p>If someone never initiates, never lingers, and never remembers, that is
information too. It does not mean you are not worth liking. It means the
feeling is probably not there, and you can let the crush soften instead of
interpreting every smile forever.</p>

<h2>A way to actually find out</h2>
<p>Asking is the only proof, and asking is exactly the thing that feels too
expensive. So there is a middle path: express interest only if it is mutual,
silently. Add them to your private list, and the next move only exists if
they picked you too. No read required.</p>
""",
    },
    {
        "slug": "the-case-for-keeping-your-crush-list-private",
        "title": "The Case for Keeping Your Crush List Private",
        "excerpt": (
            "Ranking people is normal. Ranking people in public is a disaster. "
            "Why a crush list should be the most private document you own."
        ),
        "body": """
<p>Everyone has a rough sense of who they are drawn to. Almost nobody wants
that turned into a list that other people can read.</p>

<h2>A list changes the meaning of a crush</h2>
<p>The moment your preferences are written down and visible, a feeling becomes
a scoreboard. Who made the cut, who didn't, who is first and who is third.
That ranking is not the feeling. It is an artefact of trying to organise the
feeling, and it is exactly the thing that would hurt someone if they saw it.</p>

<h2>Public lists punish honesty</h2>
<p>If people can see your list, you stop writing the truth. You write the
version that looks good, or you write nothing. A tool that makes you edit
yourself is not a tool for honest feeling.</p>

<h2>Privacy makes the yes meaningful</h2>
<p>A match only means something if the information behind it was secret until
it was mutual. If everyone can see who likes whom, there is nothing to
discover and nothing to be brave about. The secret is not a flaw in the idea.
It is the whole point.</p>

<h2>What good design does</h2>
<ul>
  <li>Stores your entries against internal ids, never exposed.</li>
  <li>Never emails, notifies or hints at the person you picked.</li>
  <li>Hides even the order of your list, because the order is the most
    hurtful part.</li>
  <li>Reveals a name only when both people have agreed.</li>
</ul>
<p>That last one is the standard worth holding. Not "private by default".
Private, until both people say otherwise.</p>
""",
    },
    {
        "slug": "college-crush-culture-why-campus-only-matters",
        "title": "College Crush Culture: Why Campus-Only Matters",
        "excerpt": (
            "A crush is easier to trust when the person is real, nearby, and "
            "verifiable. Campus-only is not a limitation — it is the feature."
        ),
        "body": """
<p>There is a specific, low-grade magic to a college crush. The same lectures,
the same corridors, the same cheap tea. You see them often enough for it to
mean something, and rarely enough for it to stay a question.</p>

<h2>Why the campus boundary is a feature</h2>
<ul>
  <li><strong>Everyone is real.</strong> No strangers from anywhere on the
    internet, no catfish, no age you cannot check.</li>
  <li><strong>A match is actionable.</strong> "It's mutual" is useful when you
    will actually pass each other tomorrow.</li>
  <li><strong>Identity can be verified.</strong> Roll numbers only make sense
    inside a single campus, which is exactly where the verifier works.</li>
  <li><strong>It stays small.</strong> A tight network makes a rumour costly
    and privacy worth respecting.</li>
</ul>

<h2>What campus-only does not mean</h2>
<p>It does not mean a public directory. The rule that a match forms only
within your campus is not the same as letting anyone browse that campus.
Those are two different things, and only one of them is allowed here. There is
no searchable list of students, ever.</p>

<h2>The harder question: what if my college isn't here?</h2>
<p>Then you add it. A few seconds at sign-up, and every other student who
looks for it will find it after you. Growth is not the goal for its own sake —
it is just what turns a solo crush into an actual, verified mutual one.</p>

<blockquote>
  <p>A match means two real people, at the same college, who both chose each
  other. That sentence is the entire product.</p>
</blockquote>
""",
    },
    {
        "slug": "what-to-do-after-a-mutual-crush-match",
        "title": "What to Do After a Mutual Crush Match",
        "excerpt": (
            "The hard part is over. Now the easy way to spoil it: pressure. "
            "A short, respectful playbook for the first few hours."
        ),
        "body": """
<p>Congratulations — the uncertainty is gone. That is a genuinely rare and
good thing, so protect it. The most common way to waste a mutual match is to
treat it as a finish line that has to be sprinted across.</p>

<h2>1. Breathe before you message</h2>
<p>You just found out. So did they, and they might need a minute. Nobody has
to prove anything in the first ten seconds after the alert lands.</p>

<h2>2. Keep it private by default</h2>
<p>It is tempting to tell the group chat. Don't, unless they are on board.
What you have is a private fact between two people, and posting it is how an
easy start becomes a public performance.</p>

<h2>3. One low-pressure message</h2>
<p>Something small and friendly beats something grand. You are checking
whether the person behind the crush is as easy to talk to as you imagined — an
ordinary conversation tells you that faster than a declaration.</p>

<h2>4. No scorekeeping</h2>
<p>Do not ask who liked whom first, and do not ask where you ranked. That
information was deliberately never shared, and it does not help anything now.
The useful fact is mutual, and you already have it.</p>

<h2>5. Take the graceful off-ramp if it fades</h2>
<p>Sometimes the answer is "mutual crush, no chemistry". That is not a
failure and not a rejection — it is exactly the information the whole exercise
was for. Treat it as a clean ending and be kind about it.</p>

<h2>6. Remember consent does not stop at the reveal</h2>
<p>You both agreed to see each other's name. That is where choice begins, not
where it ends. A match is an introduction, not an obligation.</p>
""",
    },
    {
        "slug": "secret-admirer-vs-secret-crush",
        "title": "Secret Admirer vs Secret Crush: What's the Difference?",
        "excerpt": (
            "They sound like the same thing and are almost opposites. One is "
            "about who you want; the other is about who wants you."
        ),
        "body": """
<p>People use the two phrases interchangeably. They should not, because they
point in opposite directions, and confusing them makes both harder to think
about.</p>

<h2>A secret crush: your secret</h2>
<p>You like someone and you have not told them. The secret belongs to you, you
hold it, and you control it. It is a private feeling with a public object.</p>

<h2>A secret admirer: someone else's secret</h2>
<p>Someone likes you and has not told you. Now the secret belongs to
<em>them</em>, and you are the object. You know something is going on
("signed, your secret admirer") but not who, and not why.</p>

<h2>Why the difference matters in practice</h2>
<ul>
  <li><strong>Secret crush</strong> gives you agency. You can act, wait, or
    let it go.</li>
  <li><strong>Secret admirer</strong> takes agency away. You can only guess,
    which is why anonymous admiration can feel flattering and unsettling at
    the same time.</li>
</ul>

<h2>The uncomfortable overlap</h2>
<p>If the secret admirer is someone you also like, the two situations collapse
into one mutual crush — the best possible outcome. If they are not, you are
holding a wanted secret that you cannot use. That is the messiness no
anonymous note can fix.</p>

<h2>A structure that respects both</h2>
<p>The cleanest version removes the guesswork from both sides at once. You
record your own secret crush privately, and someone does the same about you.
Nobody is told who picked whom. The name appears only in the one case where
both are true, which spares everyone the awkward half of both scenarios.</p>
""",
    },
    {
        "slug": "is-it-weird-to-have-a-crush-on-a-classmate",
        "title": "Is It Weird to Have a Crush on a Classmate?",
        "excerpt": (
            "No. It is one of the most ordinary things a person does. What "
            "matters is not the crush — it is the conduct."
        ),
        "body": """
<p>Short answer: no. You spend hours a week near the same people. Attention
and attraction are what humans do in that situation. Having the feeling is
not strange, and it is not (on its own) a problem.</p>

<h2>What actually makes it weird</h2>
<p>Not the crush. The conduct. It turns uncomfortable for everyone when a
feeling is treated as an entitlement:</p>
<ul>
  <li>When "no" is heard as "not yet".</li>
  <li>When attention continues after the person has clearly pulled back.</li>
  <li>When a private feeling becomes public pressure — a scene, a campaign, a
    group of friends enlisted to help.</li>
  <li>When proximity is used as closeness. Sharing a classroom is not
    consent to anything.</li>
</ul>

<h2>The line to hold</h2>
<p>You are free to feel whatever you feel. You are responsible for how it
shows up around another person's choices. A crush becomes a problem the
moment it stops being about your feelings and starts being about their
compliance.</p>

<h2>Keep it low-stakes</h2>
<p>Most awkward classmate situations are created by escalating a private thing
into a public one. Keeping the early stage quiet is self-protection as much as
respect: few crushes need an audience, and a quiet path to a yes (or a clean
no) is worth far more than a dramatic reveal that goes badly.</p>
""",
    },
    {
        "slug": "how-to-handle-a-crush-you-cant-act-on",
        "title": "How to Handle a Crush You Can't Act On",
        "excerpt": (
            "Sometimes the feeling is real and the timing is wrong. Here is how "
            "to carry it without making it someone else's problem."
        ),
        "body": """
<p>Not every crush is available to act on. Maybe they are involved with
someone, maybe you have a rule about dating in your department, maybe the
friendship matters more. The feeling does not get the memo just because the
answer is "not now".</p>

<h2>Start with honesty, privately</h2>
<p>You do not owe anyone a confession, but you do owe yourself a clear
picture. "I like them and I am not going to do anything about it, on purpose"
is a much more stable position than "maybe someday", which keeps you
half-invested indefinitely.</p>

<h2>Do not make your comfort their job</h2>
<p>Confessing purely to relieve your own pressure is a common and forgivable
mistake, but it is still a mistake. It transfers your discomfort onto the
person you claim to care about, who never asked for it. If acting would cost
them, don't.</p>

<h2>Things that actually help</h2>
<ul>
  <li><strong>Distance when you can take it.</strong> Fewer low-value
    encounters, not drama — just less fuel.</li>
  <li><strong>Redirect attention.</strong> Crushes shrink in the presence of
    other absorbing things: work, people, projects, sleep.</li>
  <li><strong>Say it once, to a friend.</strong> Naming a feeling tends to
    loosen it. A trusted person is enough; a public post is not.</li>
  <li><strong>Give it a date.</strong> "If nothing has changed by the end of
    term, I let it go." Open-ended crushes are the ones that last too long.</li>
</ul>

<h2>When it becomes mutual later</h2>
<p>Timing changes. A situation that is closed today may open next semester.
The low-stakes version of hanging on is simply to keep the feeling private and
be ready if the door opens — not to stand in the doorway waiting.</p>
""",
    },
    {
        "slug": "the-psychology-of-mutual-attraction",
        "title": "The Psychology of Mutual Attraction",
        "excerpt": (
            "Why do crushes so often turn out to be two-sided? Some of the "
            "reasons are genuinely interesting — and none of them are fate."
        ),
        "body": """
<p>Mutual crushes are more common than people expect. Part of that is just
arithmetic — two people have to be in the same room for anything to happen —
but a few well-studied effects make the overlap likely enough to be worth
knowing.</p>

<h2>Mere exposure</h2>
<p>We tend to like things more the more often we see them, provided the
initial impression is not negative. Shared classes are a slow, reliable
attraction machine. If you feel something for someone you sit near, there is
a decent chance the exposure runs both ways.</p>

<h2>Reciprocity of liking</h2>
<p>Finding out that someone likes you tends to make you like them more. This
is the most useful one for the whole idea behind WhoIsMyCrush: a mutual
feeling is not static, it grows once it is known. Which is also why unearned
or premature claims of interest are so corrosive — they game a real
mechanism.</p>

<h2>Uncertainty is part of the pull</h2>
<p>A little uncertainty keeps attention alive. This is why the waiting stage
of a crush feels so vivid, and why a confirmed "no" is often followed by the
feeling fading surprisingly fast. The ambiguity was doing some of the work.</p>

<h2>Similarity and proximity</h2>
<p>People are drawn to those who are similar and nearby — same background,
same interests, same corridors. College compresses all of that into a few
buildings, which is why campus is such a dense place for this particular
feeling.</p>

<h2>The honest caveat</h2>
<p>None of this is fate, and none of it guarantees anything about one specific
person. Effects describe crowds, not a particular pair. They simply mean that
"it might be mutual" is a reasonable thing to suspect — and that the only way
to turn a suspicion into a fact is to get the one piece of information you
are missing.</p>
""",
    },
    {
        "slug": "create-your-secret-profile-without-overthinking-it",
        "title": "Create your secret profile without overthinking it",
        "excerpt": "A three-minute setup, one good username, and exactly zero reasons to panic.",
        "body": """
<p>Your profile is not a job application. Nobody is grading the bio. The whole
point of a secret profile is that it gives you a safe little corner to be
curious in - so the setup should take minutes, not an entire evening.</p>

<h2>Start with the absolute basics</h2>
<p>Pick the email you actually check, choose a password you have not reused
everywhere else, and get through the confirmation step. That is the boring
part done. If you get stuck, the troubleshooting guide is more useful than
refreshing the same screen twelve times.</p>

<h2>Pick a username you can live with</h2>
<p>You do not need a username that explains your entire personality. Something
short, readable and not identical to your public handles is plenty. Avoid your
full name, your roll number, your hostel room and that one nickname only your
family uses. Future you will appreciate the restraint.</p>

<h2>Keep identifying details out of the bio</h2>
<p>A little mystery is good. A full timetable is not. Skip exact class
sections, phone numbers, home addresses and anything that would make you
obvious to someone who already knows you. If you want to mention your course
or a harmless interest, that is fine - just leave yourself some room.</p>

<h2>Check the settings people forget</h2>
<p>Before you start adding names, look at who can see your activity and what
shows up on your profile. Decide whether you want notifications on, whether
you are comfortable with matches being visible, and whether you want to keep
your list private. You can always loosen things later. Starting private is a
lot easier than trying to unshare something.</p>

<h2>You can change your mind later</h2>
<p>Usernames, bios and privacy choices are not permanent. The profile is there
to serve you, not the other way around. Set it up, use it for a week, then
adjust whatever feels off. That is the entire strategy.</p>
""",
    },
    {
        "slug": "campus-picker-tutorial-find-or-add-your-college",
        "title": "Campus picker tutorial: find or add your college",
        "excerpt": "The campus picker is the difference between a random feed and a campus feed.",
        "body": """
<p>The campus picker is one of those small features that changes the whole
experience. Choose the right campus and the site stops feeling like a giant
anonymous noticeboard. Choose nothing and you are basically browsing the
internet with extra steps.</p>

<h2>What the campus picker actually does</h2>
<p>Your campus selection tells the site which community you belong to. It
helps keep crushes, matches and suggestions relevant to the people around
you. It is not a public location check-in, and it does not put a pin on a map
with your name on it. It is just the filter that makes your feed make sense.</p>

<h2>Find your college</h2>
<ol>
<li>Open your profile or the campus picker screen.</li>
<li>Type the name of your college the way you would normally say it.</li>
<li>If the exact result appears, select it and save.</li>
<li>Check that your feed or profile now shows the correct campus.</li>
</ol>
<p>Short names usually work better than the full official title. Try the name
people actually use on campus before you try the version from the prospectus.</p>

<h2>If your college is missing</h2>
<p>Use the option to add your campus and enter the details carefully. Double
check the spelling before submitting, because a duplicate campus with a typo
is annoying for everyone. If the form asks for a city or short name, fill both
in - it makes the campus easier for other students to find later.</p>

<h2>Switching campuses without losing your list</h2>
<p>Changing your campus does not have to mean starting over. Your secret list
is tied to your account, not to the campus filter. Switch when you need to,
then switch back. If something looks empty afterward, refresh the page once
before assuming the worst.</p>

<h2>Why the campus filter matters</h2>
<p>A crush is usually local. The person you keep thinking about is probably
someone you pass in a corridor, share a lecture with or see in the canteen.
The campus picker keeps the experience close to that reality. It is a small
setting with a surprisingly big effect on how useful the site feels.</p>
""",
    },
    {
        "slug": "cant-find-your-college-quick-troubleshooting",
        "title": "Can't find your college? Quick troubleshooting",
        "excerpt": "Before you declare the campus picker broken, try these five fixes.",
        "body": """
<p>College names are messy. One website uses the full official title, another
uses a two-letter abbreviation, and the sign outside the gate uses something
completely different. If your campus is not showing up, work through these
checks in order.</p>

<h2>1. Check the spelling, then check it again</h2>
<p>Autocorrect is not your friend here. Try the name without punctuation, then
without the word "University" or "College", then with it. A missing apostrophe
or an extra space can hide a result that is already there.</p>

<h2>2. Try the name people actually use</h2>
<p>Search for the short name, the initials and the local nickname. If everyone
on campus calls it something else, there is a decent chance the listing does
too. Try the city plus the college name if the short version brings up too
many results.</p>

<h2>3. Clear the filter and start fresh</h2>
<p>Sometimes the problem is not the search - it is the filter sitting quietly
in the background. Clear any selected campus or category, reload the page and
search again. If you are on a phone, close the keyboard and check that the
search field actually contains what you typed.</p>

<h2>4. Add the campus manually</h2>
<p>If the college genuinely is not listed, use the add-campus option. Enter the
name, city and short name as accurately as you can. Wait for the new listing
to appear, then select it. Do not create a second entry just because the first
one took a minute to show up.</p>

<h2>5. Try a different browser or a hard refresh</h2>
<p>A stale page can make a working feature look broken. Refresh properly, sign
out and back in, or try another browser. If the campus still refuses to appear,
take a screenshot of the error and contact support with your account email and
the exact name you searched for.</p>

<h2>One last thing</h2>
<p>Do not panic if you cannot find your campus on the first attempt. This is a
directory problem, not a you problem. Usually it is a spelling variation, a
stale page or a genuinely missing listing - and all three have a fix.</p>
""",
    },
    {
        "slug": "5-small-website-tricks-that-make-whoismycrush-easier",
        "title": "5 small website tricks that make WhoIsMyCrush easier",
        "excerpt": "Tiny habits that save time, protect your privacy and make the site less chaotic.",
        "body": """
<p>None of these are secret cheat codes. They are just small habits that make
the site feel smoother, especially once you have been using it for a while.</p>

<h2>1. Set your campus before you browse</h2>
<p>It is the first thing to fix and the easiest thing to forget. A relevant
campus makes every other feature more useful. If the feed feels random, check
the campus picker before you start blaming the algorithm.</p>

<h2>2. Use search instead of scrolling forever</h2>
<p>The Pro Tips search is there for a reason. Search for the feeling or the
situation - "mutual", "privacy", "after a match" - rather than trying to
remember the exact title. You will find the same article in a fraction of the
time.</p>

<h2>3. Copy the link when a tip is worth keeping</h2>
<p>Every article has a copy-link button. Send it to yourself, drop it in a
private note or share it with the one friend who needs to read it. A useful
article you cannot find again is only slightly better than no article at all.</p>

<h2>4. Keep your list and your browser history separate</h2>
<p>If you share a laptop or phone, use a private window for the session or sign
out when you are done. Your account settings protect what happens inside the
site, but they cannot clean up a browser that someone else can open. A little
basic hygiene goes a long way.</p>

<h2>5. Read the privacy page before you need it</h2>
<p>Most people look for privacy settings only after something has gone wrong.
Spend two minutes now deciding what you are comfortable sharing. It is much
easier to make that call when you are calm than when you are trying to undo a
setting in a hurry.</p>

<h2>The real trick</h2>
<p>Use the site in a way that still feels like you. The campus filter, the
search, the copy button and the privacy settings are all just tools. They are
supposed to make the experience lighter - not turn it into another chore.</p>
""",
    },
]


class Command(BaseCommand):
    help = "Create or refresh the launch blog posts."

    def handle(self, *args, **options):
        now = timezone.now()
        categories = {}
        for data in CATEGORIES:
            category, _ = Category.objects.update_or_create(
                slug=data["slug"],
                defaults={
                    "name": data["name"],
                    "description": data["description"],
                    "accent": data["accent"],
                    "order": data["order"],
                },
            )
            categories[data["slug"]] = category
        total = len(POSTS)
        created_count = 0
        for index, data in enumerate(POSTS):
            # Stagger publish dates so the index reads like a real archive,
            # newest first.
            published_at = now - timedelta(
                days=NEW_POST_DAYS_AGO.get(data["slug"], index * 6)
            )
            obj, created = Post.objects.update_or_create(
                slug=data["slug"],
                defaults={
                    "title": data["title"],
                    "excerpt": data["excerpt"],
                    "body": data["body"].strip(),
                    "author_name": "WhoIsMyCrush",
                    "is_published": True,
                    "published_at": published_at,
                    "category": categories.get(
                        POST_CATEGORIES.get(data["slug"])
                    ),
                    "is_featured": data["slug"] in FEATURED_POSTS,
                },
            )
            created_count += int(created)
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {total} posts ({created_count} new, "
                f"{total - created_count} refreshed)."
            )
        )
