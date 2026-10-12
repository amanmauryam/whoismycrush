"""Seed the public blog with the launch guides.

Idempotent: safe to run repeatedly. Posts are matched on slug and updated in
place, so editing this file and re-running refreshes the live copy without
creating duplicates.
"""

from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from blog.models import Post

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
]


class Command(BaseCommand):
    help = "Create or refresh the launch blog posts."

    def handle(self, *args, **options):
        now = timezone.now()
        total = len(POSTS)
        created_count = 0
        for index, data in enumerate(POSTS):
            # Stagger publish dates so the index reads like a real archive,
            # newest first.
            published_at = now - timedelta(days=index * 6)
            obj, created = Post.objects.update_or_create(
                slug=data["slug"],
                defaults={
                    "title": data["title"],
                    "excerpt": data["excerpt"],
                    "body": data["body"].strip(),
                    "author_name": "WhoIsMyCrush",
                    "is_published": True,
                    "published_at": published_at,
                },
            )
            created_count += int(created)
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {total} posts ({created_count} new, "
                f"{total - created_count} refreshed)."
            )
        )
