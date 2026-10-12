"""Template helpers for safe, valid structured data (SEARCH requirements).

``json_script`` emits ``type="application/json"``; search engines want
``application/ld+json``. This filter therefore dumps JSON itself, escaping the
few characters (``<``, ``>``, ``&``) that could otherwise break out of the
script element, and renders one ``<script>`` per object in a list.
"""

from __future__ import annotations

import json

from django import template
from django.utils.safestring import mark_safe

register = template.Library()

_ESCAPES = {
    "<": "\\u003c",
    ">": "\\u003e",
    "&": "\\u0026",
    "\u2028": "\\u2028",
    "\u2029": "\\u2029",
}


def _dumps(value) -> str:
    dumped = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    for bad, good in _ESCAPES.items():
        dumped = dumped.replace(bad, good)
    return dumped


@register.filter(name="jsonld")
def jsonld(value):
    """Render one or more JSON-LD objects as ``application/ld+json`` scripts."""
    if not value:
        return ""
    blocks = value if isinstance(value, (list, tuple)) else [value]
    html = "".join(
        f'<script type="application/ld+json">{_dumps(block)}</script>' for block in blocks
    )
    return mark_safe(html)
