"""
Renders admin-authored Markdown (blog posts today) to HTML safe to render
with Jinja's `|safe` filter.

python-markdown passes through any raw HTML typed in the source
unmodified - so a blog post body containing a literal <script> tag would
otherwise execute in every visitor's browser. Content here is written by
admins only (not public user input), but a compromised or careless admin
account is still a real stored-XSS path against every student who reads
the post, so it's sanitized regardless of the trust level of the author.

nh3 (an allowlist HTML sanitizer) strips everything not on the allowlist
- unknown tags, all `on*` event-handler attributes, `javascript:` hrefs,
<script>/<style> content, etc. - while keeping the formatting elements
Markdown actually produces.
"""
import markdown
import nh3

_ALLOWED_TAGS = {
    "p", "br", "hr",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "strong", "em", "b", "i", "u", "s", "del", "sup", "sub",
    "ul", "ol", "li",
    "blockquote", "pre", "code",
    "a", "img",
    "table", "thead", "tbody", "tr", "th", "td",
}

_ALLOWED_ATTRIBUTES = {
    # "rel" deliberately excluded - nh3's link_rel option manages it.
    "a": {"href", "title"},
    "img": {"src", "alt", "title"},
}


def render_markdown(text: str) -> str:
    html = markdown.markdown(text, extensions=["extra"])

    return nh3.clean(
        html,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        link_rel="noopener noreferrer nofollow",
    )
