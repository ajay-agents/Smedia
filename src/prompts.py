import re

_ALLOWED_TAGS_NOTE = (
    "Format the post as an HTML fragment (not a full document) using ONLY these tags: "
    "<p>, <br>, <strong>, <em>, <ul>, <li>, <span>. "
    "Do not include <script>, <style>, <html>, <head>, <body>, <iframe>, or markdown code fences "
    "(no triple backticks) anywhere in your output."
)

_CODE_FENCE_RE = re.compile(r"^```(?:html|HTML)?\s*\n?|\n?```\s*$")
_DANGEROUS_TAG_RE = re.compile(
    r"(?is)<(script|style|iframe|object|embed|link|meta)\b[^>]*>.*?</\1>|"
    r"<(script|style|iframe|object|embed|link|meta)\b[^>]*/?>"
)


def _strip_code_fences(text: str) -> str:
    return _CODE_FENCE_RE.sub("", text.strip()).strip()


def sanitize_html(html: str) -> str:
    """Defensive cleanup of LLM-produced HTML before it's rendered or persisted."""
    return _DANGEROUS_TAG_RE.sub("", html).strip()


def _source_block(topic: str, mode: str) -> str:
    if mode == "repurpose":
        return f"Source material to repurpose into a new post:\n\"\"\"\n{topic}\n\"\"\"\n"
    return f"Topic: {topic}\n"


def _context_block(research_context: str) -> str:
    if research_context:
        return f"\n{research_context}\n"
    return "\n(No research context available — rely on general knowledge and clearly avoid inventing specific stats or quotes.)\n"


def linkedin_prompt(topic: str, research_context: str, mode: str = "topic", variants: int = 2) -> str:
    return f"""{_source_block(topic, mode)}{_context_block(research_context)}
Write {variants} distinct LinkedIn post variants based on the above.
Style: professional, storytelling/insight angle, first-person where natural, no corporate buzzwords.
Length: 150-300 words each.
Structure: a strong hook first line, a short story or insight in the body, and a closing line that invites reflection (not a hard sales CTA).
At most 3 hashtags, placed at the very end in their own <p>.
{_ALLOWED_TAGS_NOTE}

Format your output EXACTLY like this:
VARIANT 1:
<p>...</p>

VARIANT 2:
<p>...</p>
"""


def facebook_prompt(topic: str, research_context: str, mode: str = "topic", variants: int = 2) -> str:
    return f"""{_source_block(topic, mode)}{_context_block(research_context)}
Write {variants} distinct Facebook post variants based on the above.
Style: casual, conversational, friendly tone, like talking to a community — light use of emoji is fine, no jargon.
Length: 50-150 words each.
End with a simple question or light call-to-engage (e.g. "what do you think?").
{_ALLOWED_TAGS_NOTE}

Format your output EXACTLY like this:
VARIANT 1:
<p>...</p>

VARIANT 2:
<p>...</p>
"""


def instagram_prompt(topic: str, research_context: str, mode: str = "topic", variants: int = 2) -> str:
    return f"""{_source_block(topic, mode)}{_context_block(research_context)}
Write {variants} distinct Instagram caption variants based on the above.
Style: punchy, visual, engaging — short lines/line breaks are fine.
Length: under 150 words for the caption itself (not counting hashtags).
Each variant must end with 5-10 relevant hashtags in their own <p> (e.g. <p>#tag1 #tag2 #tag3</p>).
{_ALLOWED_TAGS_NOTE}

Format your output EXACTLY like this:
VARIANT 1:
<p>...</p>
<p>#hashtags...</p>

VARIANT 2:
<p>...</p>
<p>#hashtags...</p>
"""


def youtube_prompt(topic: str, research_context: str, mode: str = "topic", variants: int = 5) -> str:
    # Deliberately plain text: this is painted directly onto the thumbnail image
    # via Pillow, so HTML markup here would show up as literal characters.
    return f"""{_source_block(topic, mode)}{_context_block(research_context)}
Write {variants} short, punchy YouTube thumbnail text options for a video about the above.
Rules: each option is 2-6 words MAX, all caps preferred, high curiosity/clarity — this text will be
overlaid directly on a thumbnail image, so it must be readable at a glance. No punctuation-heavy phrasing.
Plain text only — no HTML tags, no markdown.

Format your output EXACTLY like this, one per line:
HEADLINE 1: <text>
HEADLINE 2: <text>
HEADLINE 3: <text>
"""


def parse_variants(raw_text: str) -> list:
    """Split a VARIANT-marked HTML LLM response into a list of sanitized HTML fragments."""
    raw_text = _strip_code_fences(raw_text)
    parts = re.split(r"(?i)VARIANT\s*\d+\s*:?", raw_text)
    parts = [sanitize_html(p.strip()) for p in parts if p.strip()]
    return parts if parts else [sanitize_html(raw_text)]


def html_to_plain_text(html: str) -> str:
    """Convert a generated HTML fragment into paste-ready plain text.

    The rendered preview is HTML, but LinkedIn/Facebook/Instagram compose boxes
    don't accept markup — this is what a user actually copies into them.
    """
    text = re.sub(r"(?i)<br\s*/?>", "\n", html)
    text = re.sub(r"(?i)</p>", "\n\n", text)
    text = re.sub(r"(?i)<li[^>]*>", "• ", text)
    text = re.sub(r"(?i)</li>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    entities = {
        "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&#39;": "'", "&nbsp;": " ",
    }
    for entity, replacement in entities.items():
        text = text.replace(entity, replacement)
    return text.strip()


def parse_headlines(raw_text: str) -> list:
    """Split a HEADLINE-marked LLM response into a list of short plain-text headline strings."""
    raw_text = _strip_code_fences(raw_text)
    parts = re.split(r"(?i)HEADLINE\s*\d+\s*:?", raw_text)
    headlines = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        first_line = p.splitlines()[0].strip().strip('"')
        if first_line:
            headlines.append(first_line)
    return headlines if headlines else [raw_text.strip().splitlines()[0]]
