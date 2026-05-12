"""Template filters for rendering source-provided HTML safely as plain text.

Fazaa ships its offer description / terms as HTML (`<p>`, `<ol>`, `<li>`,
`<strong>`, …). Auto-escaping renders the raw tags to the user, which
looks broken. We don't want to render the HTML as HTML (XSS surface +
Quill editor noise like `class="ql-ui"`), so we convert it to plain
text with newlines preserving paragraph/list structure. The host
template uses `whitespace-pre-line` so newlines become visual breaks.
"""
import re
import html as html_lib

from django import template
from django.utils.html import strip_tags

register = template.Library()


# Block-level tags whose closes should become a paragraph break.
_BLOCK_CLOSE = re.compile(
    r"</(?:p|div|li|ol|ul|h[1-6]|tr|blockquote|pre|section|article)\s*>",
    re.IGNORECASE,
)
_BR_TAG = re.compile(r"<br\s*/?>", re.IGNORECASE)
_LI_OPEN = re.compile(r"<li[^>]*>", re.IGNORECASE)
_MULTI_NEWLINES = re.compile(r"\n{3,}")
_TRAILING_WHITESPACE_LINES = re.compile(r"[ \t]+\n")


@register.filter(name="clean_html")
def clean_html(value: str | None) -> str:
    """Strip HTML, replacing block tags with newlines and `<li>` with `- `.

    Idempotent on text that doesn't contain markup.
    """
    if not value:
        return ""
    s = str(value)
    # Bullet hint for list items so the order survives the strip.
    s = _LI_OPEN.sub("\n- ", s)
    # Block closes -> newline.
    s = _BLOCK_CLOSE.sub("\n", s)
    # <br> -> newline.
    s = _BR_TAG.sub("\n", s)
    # Remove anything that's still a tag.
    s = strip_tags(s)
    # strip_tags leaves named entities; unescape them too.
    s = html_lib.unescape(s)
    # Tidy whitespace.
    s = _TRAILING_WHITESPACE_LINES.sub("\n", s)
    s = _MULTI_NEWLINES.sub("\n\n", s)
    return s.strip()
