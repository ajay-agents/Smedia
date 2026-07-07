import logging

import streamlit as st

from src import db, llm, prompts, research, thumbnail
from src.config import get_secret

logging.basicConfig(level=logging.INFO)

st.set_page_config(page_title="Social Media Content Agent", page_icon="\U0001F4E3", layout="wide")

db.init_db()

TEXT_PLATFORMS = [
    ("linkedin", "LinkedIn", prompts.linkedin_prompt),
    ("facebook", "Facebook", prompts.facebook_prompt),
    ("instagram", "Instagram", prompts.instagram_prompt),
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
    progress = st.progress(0.0, text="Generating content...")
    total_steps = len(TEXT_PLATFORMS) + 1

    for i, (platform_key, _display, prompt_fn) in enumerate(TEXT_PLATFORMS):
        prompt = prompt_fn(topic, context, mode=mode, variants=num_variants)
        try:
            result = llm.generate_content(prompt, platform=platform_key)
        except llm.LLMError as e:
            st.session_state["generated"][platform_key] = {"error": str(e)}
            progress.progress((i + 1) / total_steps, text=f"{platform_key} failed")
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
        progress.progress((i + 1) / total_steps, text=f"{platform_key} done ({result['provider_used']})")

    # YouTube headline options
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
    except llm.LLMError as e:
        st.session_state["youtube_data"] = {"error": str(e)}

    progress.progress(1.0, text="Done")
    st.session_state["last_topic"] = topic
    st.session_state["last_mode"] = mode


def render_text_platform_tab(platform_key: str, display_name: str, prompt_fn):
    data = st.session_state["generated"].get(platform_key)
    if not data:
        st.info("Generate content above to see drafts here.")
        return
    if data.get("error"):
        st.error(f"Generation failed for {display_name}: {data['error']}")
        return

    st.caption(f"Provider used: `{data['provider_used']}`")

    for idx, variant in enumerate(data["variants"]):
        st.markdown(f"**Variant {idx + 1}**")
        edit_key = f"{platform_key}_edit_{variant['row_id']}"
        st.text_area("Edit before approving", value=variant["text"], key=edit_key, height=180, label_visibility="collapsed")

        col1, col2, col3 = st.columns([1, 1, 4])
        if col1.button("Approve", key=f"approve_{platform_key}_{variant['row_id']}"):
            db.update_generation(variant["row_id"], approval_status="approved", edited_content=st.session_state[edit_key])
            st.success("Approved and saved.")
        if col2.button("Reject", key=f"reject_{platform_key}_{variant['row_id']}"):
            db.update_generation(variant["row_id"], approval_status="rejected")
            st.info("Rejected.")
        st.divider()

    if st.button(f"Regenerate {display_name}", key=f"regen_{platform_key}"):
        topic = st.session_state["last_topic"]
        mode = st.session_state["last_mode"]
        prompt = prompt_fn(topic, st.session_state["research_context"], mode=mode, variants=len(data["variants"]) or 2)
        try:
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
            st.rerun()
        except llm.LLMError as e:
            st.error(f"Regeneration failed: {e}")


def render_youtube_tab():
    data = st.session_state["youtube_data"]
    if not data:
        st.info("Generate content above to see thumbnail headline options here.")
        return
    if data.get("error"):
        st.error(f"Headline generation failed: {data['error']}")
        return

    st.caption(f"Provider used: `{data['provider_used']}`")
    headline = st.radio("Choose a headline", data["headlines"], key="yt_headline_choice")
    template = st.radio("Choose a background template", list(thumbnail.TEMPLATES.keys()), horizontal=True, key="yt_template_choice")

    if st.button("Generate Thumbnail"):
        path = thumbnail.generate_thumbnail(headline, template=template)
        st.session_state["thumbnail_path"] = path

    if st.session_state["thumbnail_path"]:
        st.image(st.session_state["thumbnail_path"], width=640)
        with open(st.session_state["thumbnail_path"], "rb") as f:
            image_bytes = f.read()
        col1, col2 = st.columns([1, 1])
        col1.download_button("Download PNG", data=image_bytes, file_name="thumbnail.png", mime="image/png")
        if col2.button("Approve thumbnail"):
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
            st.success("Thumbnail approved and saved to history.")


def render_history_tab():
    col1, col2 = st.columns(2)
    platform_filter = col1.selectbox("Platform", ["All", "linkedin", "facebook", "instagram", "youtube"])
    status_filter = col2.selectbox("Status", ["All", "pending", "approved", "rejected"])

    rows = db.get_history(
        platform=None if platform_filter == "All" else platform_filter,
        approval_status=None if status_filter == "All" else status_filter,
    )
    if not rows:
        st.info("No generations yet.")
        return

    for row in rows:
        with st.expander(f"[{row['platform']}] {row['topic'][:60]} — {row['approval_status']} — {row['created_at']}"):
            st.caption(f"Provider: {row['provider_used']} | Mode: {row['mode']} | Variant #{row['variant_index']}")
            if row["content_type"] == "image":
                st.image(row["content"], width=480)
            else:
                st.text(row["edited_content"] or row["content"])


st.title("\U0001F4E3 Social Media Content Agent")
st.caption("Topic in → research → platform-tailored drafts out. Nothing is auto-posted; you review and approve everything.")

with st.sidebar:
    st.header("Status")
    st.write("Gemini key:", "✅" if get_secret("GEMINI_API_KEY") else "❌ missing")
    st.write("OpenAI key:", "✅" if get_secret("OPENAI_API_KEY") else "❌ missing")
    st.write("Tavily key:", "✅" if get_secret("TAVILY_API_KEY") else "❌ missing")
    st.divider()
    force_failure = st.checkbox("Force Gemini failure (test OpenAI fallback)", value=False)
    llm.set_force_gemini_failure(force_failure)
    num_variants = st.slider("Variants per platform", min_value=1, max_value=3, value=2)

mode_choice = st.radio("Input type", ["Topic / keyword", "Paste existing content to repurpose"], horizontal=True)
mode = "repurpose" if mode_choice.startswith("Paste") else "topic"
placeholder = "e.g. an existing blog post or article to repurpose..." if mode == "repurpose" else "e.g. why small teams should adopt AI code review"
topic_input = st.text_area("Topic / content", placeholder=placeholder, height=120)

if st.button("Generate", type="primary"):
    if not topic_input or not topic_input.strip():
        st.error("Please enter a topic or paste content before generating.")
    else:
        run_generation(topic_input.strip(), mode, num_variants)

if st.session_state["research_warning"]:
    st.warning(f"Research step failed, continuing without research context: {st.session_state['research_warning']}")

tab_li, tab_fb, tab_ig, tab_yt, tab_hist = st.tabs(["LinkedIn", "Facebook", "Instagram", "YouTube", "History"])

with tab_li:
    render_text_platform_tab("linkedin", "LinkedIn", prompts.linkedin_prompt)
with tab_fb:
    render_text_platform_tab("facebook", "Facebook", prompts.facebook_prompt)
with tab_ig:
    render_text_platform_tab("instagram", "Instagram", prompts.instagram_prompt)
with tab_yt:
    render_youtube_tab()
with tab_hist:
    render_history_tab()
