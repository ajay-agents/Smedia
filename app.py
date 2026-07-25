import logging

import streamlit as st
import streamlit.components.v1 as components

from src import db, llm, prompts, research, thumbnail
from src.config import get_secret

logging.basicConfig(level=logging.INFO)

st.set_page_config(page_title="ContentForge AI", page_icon="\U0001F680", layout="wide")

PLATFORM_META = {
    "linkedin": {"label": "LinkedIn", "emoji": "\U0001F4BC", "color": "#0A66C2", "cook": "Polishing your professional glow-up"},
    "facebook": {"label": "Facebook", "emoji": "\U0001F4D8", "color": "#1877F2", "cook": "Brewing something friend-group-worthy"},
    "instagram": {"label": "Instagram", "emoji": "\U0001F4F8", "color": "#DD2A7B", "cook": "Making it aesthetic"},
    "youtube": {"label": "YouTube", "emoji": "▶️", "color": "#FF0000", "cook": "Crafting thumbnail-worthy hooks"},
}

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@600;700;800&family=Inter:wght@400;500;600&display=swap');

html, body, [class^="css"], [class*=" css"] { font-family: 'Inter', sans-serif; }

.hero-wrap { text-align: center; padding: 0.4rem 0 1rem 0; }
.hero-title {
    font-family: 'Poppins', sans-serif;
    font-weight: 800;
    font-size: 2.7rem;
    background: linear-gradient(90deg, #7C3AED, #EC4899, #F59E0B);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0;
}
.hero-sub { color: #6B7280; font-size: 1.02rem; margin-top: 0.35rem; }

.variant-badge {
    display: inline-block;
    padding: 0.15rem 0.7rem;
    border-radius: 999px;
    font-weight: 700;
    font-size: 0.8rem;
    color: white;
}

div.stButton > button {
    border-radius: 999px !important;
    font-weight: 600 !important;
    border: none !important;
    padding: 0.5rem 1.3rem !important;
    transition: transform 0.12s ease, box-shadow 0.12s ease !important;
}
div.stButton > button:hover { transform: translateY(-1px) scale(1.02); box-shadow: 0 6px 16px rgba(124, 58, 237, 0.25); }
div.stButton > button[kind="primary"] {
    background: linear-gradient(90deg, #7C3AED, #EC4899) !important;
    color: white !important;
}

button[data-baseweb="tab"] { font-weight: 700 !important; font-size: 1.02rem !important; }

[data-testid="stMetric"] {
    background: linear-gradient(135deg, rgba(124,58,237,0.08), rgba(236,72,153,0.08));
    border-radius: 14px;
    padding: 0.5rem 0.8rem;
    border: 1px solid rgba(124,58,237,0.15);
}

[data-testid="stSidebar"] { background: linear-gradient(180deg, rgba(124,58,237,0.06), rgba(236,72,153,0.03)); }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

db.init_db()

TEXT_PLATFORMS = [
    ("linkedin", prompts.linkedin_prompt),
    ("facebook", prompts.facebook_prompt),
    ("instagram", prompts.instagram_prompt),
]

DEFAULTS = {
    "generated": {},          # platform -> {"variants": [{"row_id", "text"}], "provider_used": str}
    "research_context": "",
    "research_warning": None,
    "last_topic": "",
    "last_mode": "topic",
    "youtube_data": None,     # {"row_ids": [...], "headlines": [...], "provider_used": str}
    "thumbnail_path": None,
}
for key, default in DEFAULTS.items():
    st.session_state.setdefault(key, default)


def run_generation(topic: str, mode: str, num_variants: int):
    st.session_state["generated"] = {}
    st.session_state["youtube_data"] = None
    st.session_state["thumbnail_path"] = None
    st.session_state["research_warning"] = None

    # FR2: research failure must not block generation.
    try:
        results = research.research_topic(topic)
        st.session_state["research_context"] = research.format_research_context(results)
    except research.ResearchError as e:
        st.session_state["research_context"] = ""
        st.session_state["research_warning"] = str(e)

    context = st.session_state["research_context"]
    progress = st.progress(0.0, text="Warming up the content engine... \U0001F525")
    total_steps = len(TEXT_PLATFORMS) + 1
    any_success = False

    for i, (platform_key, prompt_fn) in enumerate(TEXT_PLATFORMS):
        meta = PLATFORM_META[platform_key]
        prompt = prompt_fn(topic, context, mode=mode, variants=num_variants)
        try:
            result = llm.generate_content(prompt, platform=platform_key)
        except llm.LLMError as e:
            st.session_state["generated"][platform_key] = {"error": str(e)}
            progress.progress((i + 1) / total_steps, text=f"{meta['emoji']} {meta['label']} hit a snag, skipping...")
            continue

        variants = prompts.parse_variants(result["text"])
        variant_rows = []
        for idx, text in enumerate(variants):
            row_id = db.save_generation(
                topic=topic,
                mode=mode,
                platform=platform_key,
                variant_index=idx,
                content_type="text",
                content=text,
                provider_used=result["provider_used"],
            )
            variant_rows.append({"row_id": row_id, "text": text})

        st.session_state["generated"][platform_key] = {
            "variants": variant_rows,
            "provider_used": result["provider_used"],
            "error": None,
        }
        any_success = True
        progress.progress((i + 1) / total_steps, text=f"{meta['emoji']} {meta['label']} done via {result['provider_used']}!")

    # YouTube headline options
    yt_meta = PLATFORM_META["youtube"]
    progress.progress(min(0.95, (len(TEXT_PLATFORMS)) / total_steps), text=f"{yt_meta['emoji']} {yt_meta['cook']}...")
    yt_prompt = prompts.youtube_prompt(topic, context, mode=mode, variants=5)
    try:
        yt_result = llm.generate_content(yt_prompt, platform="youtube")
        headlines = prompts.parse_headlines(yt_result["text"])
        row_ids = [
            db.save_generation(
                topic=topic,
                mode=mode,
                platform="youtube",
                variant_index=idx,
                content_type="text",
                content=h,
                provider_used=yt_result["provider_used"],
            )
            for idx, h in enumerate(headlines)
        ]
        st.session_state["youtube_data"] = {
            "row_ids": row_ids,
            "headlines": headlines,
            "provider_used": yt_result["provider_used"],
            "error": None,
        }
        any_success = True
    except llm.LLMError as e:
        st.session_state["youtube_data"] = {"error": str(e)}

    progress.progress(1.0, text="\U0001F389 All done! Scroll down to review your drafts.")
    st.session_state["last_topic"] = topic
    st.session_state["last_mode"] = mode
    if any_success:
        st.balloons()


def render_html_preview(html_content: str, height: int = 260, accent_color: str = "#7C3AED"):
    wrapper = f"""
    <div style="font-family: -apple-system, 'Segoe UI', Roboto, Arial, sans-serif;
                font-size: 15px; line-height: 1.5; color: #111827; background: #ffffff;
                padding: 16px; border: 1px solid #e5e7eb; border-left: 5px solid {accent_color};
                border-radius: 10px; box-sizing: border-box; word-wrap: break-word;">
    {html_content}
    </div>
    """
    components.html(wrapper, height=height, scrolling=True)


def render_text_platform_tab(platform_key: str, prompt_fn):
    meta = PLATFORM_META[platform_key]
    data = st.session_state["generated"].get(platform_key)
    if not data:
        st.info(f"Hit **Generate** above to get your {meta['label']} drafts \U0001F440")
        return
    if data.get("error"):
        st.error(f"{meta['emoji']} {meta['label']} generation failed: {data['error']}")
        return

    st.caption(f"Served by `{data['provider_used']}`")
    preview_height = {"linkedin": 320, "facebook": 220, "instagram": 260}.get(platform_key, 260)

    for idx, variant in enumerate(data["variants"]):
        with st.container(border=True):
            st.markdown(
                f'<span class="variant-badge" style="background:{meta["color"]}">Variant {idx + 1}</span>',
                unsafe_allow_html=True,
            )
            edit_key = f"{platform_key}_edit_{variant['row_id']}"

            st.caption("\U0001F441️ Preview")
            render_html_preview(
                st.session_state.get(edit_key, variant["text"]), height=preview_height, accent_color=meta["color"]
            )

            st.caption("\U0001F58A️ HTML source (editable)")
            st.text_area("Edit before approving", value=variant["text"], key=edit_key, height=140, label_visibility="collapsed")

            col1, col2, col3 = st.columns([1, 1, 4])
            if col1.button("✅ Approve", key=f"approve_{platform_key}_{variant['row_id']}"):
                db.update_generation(variant["row_id"], approval_status="approved", edited_content=st.session_state[edit_key])
                st.toast(f"{meta['emoji']} {meta['label']} variant approved & saved!", icon="\U0001F389")
            if col2.button("\U0001F5D1️ Reject", key=f"reject_{platform_key}_{variant['row_id']}"):
                db.update_generation(variant["row_id"], approval_status="rejected")
                st.toast("Rejected — no hard feelings, try regenerating!", icon="\U0001F5D1️")

    if st.button(f"\U0001F504 Regenerate {meta['label']}", key=f"regen_{platform_key}"):
        topic = st.session_state["last_topic"]
        mode = st.session_state["last_mode"]
        prompt = prompt_fn(topic, st.session_state["research_context"], mode=mode, variants=len(data["variants"]) or 2)
        try:
            with st.spinner(f"{meta['cook']}..."):
                result = llm.generate_content(prompt, platform=platform_key)
            variants = prompts.parse_variants(result["text"])
            variant_rows = []
            for idx, text in enumerate(variants):
                row_id = db.save_generation(
                    topic=topic, mode=mode, platform=platform_key, variant_index=idx,
                    content_type="text", content=text, provider_used=result["provider_used"],
                )
                variant_rows.append({"row_id": row_id, "text": text})
            st.session_state["generated"][platform_key] = {
                "variants": variant_rows, "provider_used": result["provider_used"], "error": None,
            }
            st.toast(f"Fresh {meta['label']} variants coming right up!", icon="\U0001F504")
            st.rerun()
        except llm.LLMError as e:
            st.error(f"Regeneration failed: {e}")


def render_youtube_tab():
    meta = PLATFORM_META["youtube"]
    data = st.session_state["youtube_data"]
    if not data:
        st.info("Hit **Generate** above to get thumbnail headline options \U0001F440")
        return
    if data.get("error"):
        st.error(f"Headline generation failed: {data['error']}")
        return

    st.caption(f"Served by `{data['provider_used']}`")
    headline = st.radio("\U0001F3AF Pick a headline", data["headlines"], key="yt_headline_choice")

    template_labels = {"midnight": "\U0001F30C Midnight", "sunset": "\U0001F305 Sunset", "forest": "\U0001F33F Forest"}
    template = st.radio(
        "\U0001F3A8 Pick a vibe",
        list(thumbnail.TEMPLATES.keys()),
        format_func=lambda k: template_labels.get(k, k),
        horizontal=True,
        key="yt_template_choice",
    )

    if st.button("\U0001F5BC️ Generate Thumbnail", type="primary"):
        path = thumbnail.generate_thumbnail(headline, template=template)
        st.session_state["thumbnail_path"] = path

    if st.session_state["thumbnail_path"]:
        st.image(st.session_state["thumbnail_path"], width=640)
        with open(st.session_state["thumbnail_path"], "rb") as f:
            image_bytes = f.read()
        col1, col2 = st.columns([1, 1])
        col1.download_button("⬇️ Download PNG", data=image_bytes, file_name="thumbnail.png", mime="image/png")
        if col2.button("✅ Approve thumbnail"):
            db.save_generation(
                topic=st.session_state["last_topic"],
                mode=st.session_state["last_mode"],
                platform="youtube",
                variant_index=0,
                content_type="image",
                content=st.session_state["thumbnail_path"],
                provider_used=data["provider_used"],
                approval_status="approved",
            )
            st.toast("Thumbnail approved & saved to history!", icon="\U0001F389")
            st.balloons()


def render_history_tab():
    col1, col2 = st.columns(2)
    platform_filter = col1.selectbox("Platform", ["All", "linkedin", "facebook", "instagram", "youtube"])
    status_filter = col2.selectbox("Status", ["All", "pending", "approved", "rejected"])

    rows = db.get_history(
        platform=None if platform_filter == "All" else platform_filter,
        approval_status=None if status_filter == "All" else status_filter,
    )
    if not rows:
        st.info("Nothing here yet — go generate some content! \U0001F31F")
        return

    status_emoji = {"pending": "⏳", "approved": "✅", "rejected": "\U0001F5D1️"}
    for row in rows:
        meta = PLATFORM_META.get(row["platform"], {"emoji": "\U0001F4C4", "color": "#7C3AED"})
        label = f"{meta['emoji']} {row['topic'][:60]} — {status_emoji.get(row['approval_status'], '')} {row['approval_status']} — {row['created_at']}"
        with st.expander(label):
            st.caption(f"Provider: {row['provider_used']} | Mode: {row['mode']} | Variant #{row['variant_index']}")
            if row["content_type"] == "image":
                st.image(row["content"], width=480)
            elif row["platform"] == "youtube":
                st.text(row["edited_content"] or row["content"])
            else:
                render_html_preview(row["edited_content"] or row["content"], height=220, accent_color=meta["color"])


st.markdown(
    """
    <div class="hero-wrap">
        <div class="hero-title">\U0001F680 ContentForge AI</div>
        <div class="hero-sub">Drop a topic, we'll cook up scroll-stopping drafts for LinkedIn, Facebook, Instagram & a YouTube
        thumbnail. Nothing posts itself — you approve every single thing.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

all_rows = db.get_history(limit=2000)
approved_count = sum(1 for r in all_rows if r["approval_status"] == "approved")
pending_count = sum(1 for r in all_rows if r["approval_status"] == "pending")
topics_count = len(db.get_distinct_topics(limit=2000))

stat_cols = st.columns(3)
stat_cols[0].metric("\U0001F525 Approved", approved_count)
stat_cols[1].metric("⏳ Awaiting review", pending_count)
stat_cols[2].metric("\U0001F4DA Topics explored", topics_count)

with st.sidebar:
    st.markdown("### \U0001F39B️ Control Panel")
    st.caption("Quick vibe check on your AI crew")
    st.write("Gemini \U0001F916", "✅ ready" if get_secret("GEMINI_API_KEY") else "❌ missing key")
    st.write("Groq ⚡", "✅ ready" if get_secret("GROQ_API_KEY") else "❌ missing key")
    st.write("Tavily \U0001F50D", "✅ ready" if get_secret("TAVILY_API_KEY") else "❌ missing key")
    st.divider()
    st.markdown("**\U0001F9EA Fallback test mode**")
    force_failure = st.checkbox("Force Gemini to fail (watch Groq save the day)", value=False)
    llm.set_force_gemini_failure(force_failure)
    st.markdown("**\U0001F3DA️ Variants per platform**")
    num_variants = st.slider("Variants per platform", min_value=1, max_value=3, value=2, label_visibility="collapsed")

mode_choice = st.radio("Input type", ["\U0001F4A1 Topic / keyword", "\U0001F4CB Paste content to repurpose"], horizontal=True)
mode = "repurpose" if "Paste" in mode_choice else "topic"
placeholder = "e.g. an existing blog post or article to repurpose..." if mode == "repurpose" else "e.g. why small teams should adopt AI code review"
topic_input = st.text_area("Topic / content", placeholder=placeholder, height=120, label_visibility="collapsed")

if st.button("✨ Generate My Content", type="primary"):
    if not topic_input or not topic_input.strip():
        st.error("Give me something to work with first! Enter a topic or paste some content \U0001F447")
    else:
        run_generation(topic_input.strip(), mode, num_variants)

if st.session_state["research_warning"]:
    st.warning(f"Research step whiffed, continuing without it: {st.session_state['research_warning']}")

tab_li, tab_fb, tab_ig, tab_yt, tab_hist = st.tabs(
    ["\U0001F4BC LinkedIn", "\U0001F4D8 Facebook", "\U0001F4F8 Instagram", "▶️ YouTube", "\U0001F553 History"]
)

with tab_li:
    render_text_platform_tab("linkedin", prompts.linkedin_prompt)
with tab_fb:
    render_text_platform_tab("facebook", prompts.facebook_prompt)
with tab_ig:
    render_text_platform_tab("instagram", prompts.instagram_prompt)
with tab_yt:
    render_youtube_tab()
with tab_hist:
    render_history_tab()
