"""
Renders admin-authored Markdown (blog posts today) to HTML safe to render
with Jinja's `|safe` filter.

python-markdown passes through any raw HTML typed in the source
unmodified - so a blog post body containing a literal <script> tag would
otherwise execute in every visitor's browser. Content here is written by
admins only (not public user input), but a compromised or careless admin
account is still a real stored-XSS path against every student who reads
the post, so it's sanitized regardless of the trust level of the author.

bleach (an allowlist HTML sanitizer) strips everything not on the
allowlist - unknown tags, all `on*` event-handler attributes,
`javascript:` hrefs, <script>/<style> content, etc. - while keeping the
formatting elements Markdown actually produces.
"""
import re

import markdown
import bleach

_ALLOWED_TAGS = {
    "p", "br", "hr",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "strong", "em", "b", "i", "u", "s", "del", "sup", "sub",
    "ul", "ol", "li",
    "blockquote", "pre", "code",
    "a", "img",
    "table", "thead", "tbody", "tr", "th", "td",
}

_LINK_REL = "noopener noreferrer nofollow"

_ALLOWED_ATTRIBUTES = {
    "a": {"href", "title"},
    "img": {"src", "alt", "title"},
}


def render_markdown(text: str) -> str:
    html = markdown.markdown(text, extensions=["extra"])

    cleaned = bleach.clean(
        html,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        strip=True,
    )
    # bleach has no built-in equivalent of nh3's link_rel option, so <a>
    # tags get rel="noopener noreferrer nofollow" added by hand.
    return re.sub(r"<a\b", f'<a rel="{_LINK_REL}"', cleaned)
