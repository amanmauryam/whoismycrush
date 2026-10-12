"""Editorial content for the public marketing pages.

Kept in Python rather than the database: these are stable, code-reviewed pages
whose copy must ship with the app. The blog (a separate app) is where
editable, dated articles live.
"""

from __future__ import annotations

# FAQ — every answer here is also rendered visibly on /faq/, so the FAQPage
# structured data can never describe something a reader cannot see.
FAQ_GROUPS: list[dict] = [
    {
        "title": "The basics",
        "items": [
            (
                "What is WhoIsMyCrush?",
                "A private, college-only game. You type up to three people you "
                "secretly like, seal the list, and wait. If someone you picked "
                "picked you too, we let you both know — but only after a real "
                "person has verified the match.",
            ),
            (
                "Is this a dating app?",
                "No. There is no swiping, no feed, no likes, no followers and no "
                "chat in the MVP. There is no student search either — you type "
                "names by hand. The whole product is a sealed list and the "
                "possibility that it becomes mutual.",
            ),
            (
                "Who can use it?",
                "Students aged 18 and over who study at a college on the "
                "platform. You build a private campus ID when you sign up, and "
                "crushes only ever match inside the same campus.",
            ),
        ],
    },
    {
        "title": "Privacy",
        "items": [
            (
                "Can anyone see my crush list?",
                "No. Not other students, and not the person you picked. Your list, "
                "your order and the fact that you picked anyone at all stay "
                "sealed. Only the reviewing admin can see the entries, and only "
                "to check a possible match.",
            ),
            (
                "Will they know I added them?",
                "No. Adding someone is completely silent. They only ever hear "
                "from us if you both picked each other and the match was "
                "verified.",
            ),
            (
                "Does my #1, #2 or #3 mean anything?",
                "No. The order is stored only so you can manage your own list. It "
                "is never shown to the other person, never put in a notification, "
                "and never used to rank anyone.",
            ),
        ],
    },
    {
        "title": "Matching",
        "items": [
            (
                "My crush doesn't have an account yet. Can I still add them?",
                "Yes. Add them with the details you know. If they join later and "
                "pick you back, the match is detected then. They never have to "
                "know you added them first.",
            ),
            (
                "How do you know it's the same person?",
                "Campus and roll number are the identity gate — both must line "
                "up. Name, course, year and section are used to corroborate and "
                "to queue the match for review. A similar name alone can never "
                "create a match.",
            ),
            (
                "Why does a person review every match?",
                "Hand-typed details can collide (two students, same roll, "
                "different spelling). A human approves each pair before anyone is "
                "notified, which is what keeps false matches out and your secret "
                "safe.",
            ),
        ],
    },
    {
        "title": "Reveal and roses",
        "items": [
            (
                "Do I have to reveal myself?",
                "Never. When a match is confirmed, both of you can choose to "
                "reveal. Identities only appear if both sides agree. Either of "
                "you can also close a match and stay anonymous.",
            ),
            (
                "Do roses cost anything, and are they required?",
                "Roses are an optional extra and are not live yet. Matching and "
                "revealing are always free — a rose can never unlock a match or "
                "affect whether you get one.",
            ),
        ],
    },
]


def faq_pairs() -> list[tuple[str, str]]:
    return [pair for group in FAQ_GROUPS for pair in group["items"]]
