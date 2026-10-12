"""A small, dependency-free HTML sanitizer.

Blog and guide bodies are authored by trusted staff, but we still never
render raw HTML straight from the database. This module keeps a strict
allow-list of tags/attributes and refuses unsafe URL schemes, so a stray
``<script>`` or ``javascript:`` link can never reach a page.
"""

from __future__ import annotations

from html import escape
from html.parser import HTMLParser

ALLOWED_TAGS = {
    "p",
    "br",
    "hr",
    "h2",
    "h3",
    "h4",
    "strong",
    "b",
    "em",
    "i",
    "u",
    "s",
    "ul",
    "ol",
    "li",
    "blockquote",
    "a",
    "code",
    "pre",
    "figure",
    "figcaption",
    "img",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
    "span",
}

ALLOWED_ATTRS = {
    "a": {"href", "title"},
    "img": {"src", "alt", "title", "width", "height"},
    "span": {"class"},
}

VOID_TAGS = {"br", "hr", "img"}

#: Elements whose entire contents must be thrown away, not just the tags.
#: Keeping the inner text of a ``<script>`` would still leak code into the page.
DROP_CONTENT_TAGS = {
    "script",
    "style",
    "noscript",
    "template",
    "iframe",
    "object",
    "embed",
    "title",
    "textarea",
}

_SAFE_SCHEMES = ("http://", "https://", "mailto:", "tel:")


def _safe_url(url: str | None) -> str | None:
    if not url:
        return None
    candidate = url.strip()
    if not candidate:
        return None
    lowered = candidate.lower()
    if lowered.startswith("/") or lowered.startswith("#"):
        return candidate
    if lowered.startswith(_SAFE_SCHEMES):
        return candidate
    return None


class _Sanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._open: list[str] = []
        self._skip: str | None = None

    def _clean_attrs(self, tag: str, attrs: list[tuple[str, str | None]]) -> str:
        allowed = ALLOWED_ATTRS.get(tag, set())
        rendered: list[str] = []
        for name, value in attrs:
            name = name.lower()
            if name not in allowed or value is None:
                continue
            if name in {"href", "src"}:
                safe = _safe_url(value)
                if safe is None:
                    continue
                value = safe
            rendered.append(f'{name}="{escape(value, quote=True)}"')
            if tag == "a" and name == "href":
                rendered.append('rel="nofollow noopener noreferrer"')
        return (" " + " ".join(rendered)) if rendered else ""

    def handle_starttag(self, tag, attrs):
        if self._skip is not None or tag in DROP_CONTENT_TAGS:
            if tag in DROP_CONTENT_TAGS:
                self._skip = tag
            return
        if tag not in ALLOWED_TAGS:
            return
        self.parts.append(f"<{tag}{self._clean_attrs(tag, attrs)}>")
        if tag not in VOID_TAGS:
            self._open.append(tag)

    def handle_startendtag(self, tag, attrs):
        if self._skip is not None:
            return
        if tag in ALLOWED_TAGS and tag in VOID_TAGS:
            self.parts.append(f"<{tag}{self._clean_attrs(tag, attrs)}>")

    def handle_endtag(self, tag):
        if self._skip is not None:
            if tag == self._skip:
                self._skip = None
            return
        if tag not in ALLOWED_TAGS or tag in VOID_TAGS:
            return
        if tag in self._open:
            while self._open:
                top = self._open.pop()
                self.parts.append(f"</{top}>")
                if top == tag:
                    break

    def handle_data(self, data):
        if self._skip is not None:
            return
        self.parts.append(escape(data))

    def result(self) -> str:
        while self._open:
            self.parts.append(f"</{self._open.pop()}>")
        return "".join(self.parts)


def sanitize_html(value: str) -> str:
    """Return ``value`` with all but a safe subset of HTML removed."""
    if not value:
        return ""
    parser = _Sanitizer()
    parser.feed(value)
    parser.close()
    return parser.result()
