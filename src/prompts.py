import re


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
At most 3 hashtags, placed at the very end.

Format your output EXACTLY like this:
VARIANT 1:
<post text>

VARIANT 2:
<post text>
"""


def facebook_prompt(topic: str, research_context: str, mode: str = "topic", variants: int = 2) -> str:
    return f"""{_source_block(topic, mode)}{_context_block(research_context)}
Write {variants} distinct Facebook post variants based on the above.
Style: casual, conversational, friendly tone, like talking to a community — light use of emoji is fine, no jargon.
Length: 50-150 words each.
End with a simple question or light call-to-engage (e.g. "what do you think?").

Format your output EXACTLY like this:
VARIANT 1:
<post text>

VARIANT 2:
<post text>
"""


def instagram_prompt(topic: str, research_context: str, mode: str = "topic", variants: int = 2) -> str:
    return f"""{_source_block(topic, mode)}{_context_block(research_context)}
Write {variants} distinct Instagram caption variants based on the above.
Style: punchy, visual, engaging — short lines/line breaks are fine.
Length: under 150 words for the caption itself (not counting hashtags).
Each variant must end with 5-10 relevant hashtags on their own line.

Format your output EXACTLY like this:
VARIANT 1:
<caption text>
<hashtags>

VARIANT 2:
<caption text>
<hashtags>
"""


def youtube_prompt(topic: str, research_context: str, mode: str = "topic", variants: int = 5) -> str:
    return f"""{_source_block(topic, mode)}{_context_block(research_context)}
Write {variants} short, punchy YouTube thumbnail text options for a video about the above.
Rules: each option is 2-6 words MAX, all caps preferred, high curiosity/clarity — this text will be
overlaid directly on a thumbnail image, so it must be readable at a glance. No punctuation-heavy phrasing.

Format your output EXACTLY like this, one per line:
HEADLINE 1: <text>
HEADLINE 2: <text>
HEADLINE 3: <text>
"""


def parse_variants(raw_text: str) -> list:
    """Split a VARIANT-marked LLM response into a list of variant strings."""
    parts = re.split(r"(?i)VARIANT\s*\d+\s*:?", raw_text)
    parts = [p.strip() for p in parts if p.strip()]
    return parts if parts else [raw_text.strip()]


def parse_headlines(raw_text: str) -> list:
    """Split a HEADLINE-marked LLM response into a list of short headline strings."""
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
