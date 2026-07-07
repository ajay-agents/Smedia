# Social Media Content Agent

A portfolio-grade AI agent that takes a topic (or existing content to repurpose), researches it on
the web, and generates platform-tailored drafts for **LinkedIn**, **Facebook**, **Instagram**, and
a **YouTube thumbnail** — with a human review step before anything is finalized. There is no
auto-posting to any platform.

## Features

- **Topic input** — enter a topic/niche, or paste existing long-form content to repurpose.
- **Web research** — Tavily search pulls 3-5 recent sources into the generation context; if
  research fails, generation still proceeds with a visible warning (no hard dependency).
- **Platform-specific generation** — one shared research context, four tailored prompt templates
  (tone/length/format per platform), 1-3 variants each.
- **LLM fallback** — Gemini (free tier) is tried first; on any failure it automatically falls back
  to OpenAI, behind one `generate_content(prompt, platform)` function. The provider actually used
  is logged per generation.
- **YouTube thumbnail** — Pillow composites a bold text headline over one of several preset
  gradient background templates, exported as a downloadable PNG.
- **Review UI** — Streamlit tabs per platform: edit the draft, then Approve/Reject/Regenerate.
- **Persistence** — every variant (topic, platform, content, provider used, approval status,
  timestamp) is saved to SQLite, with a History tab to browse past generations.

## Project layout

```
app.py                 Streamlit UI — input, tabs, review/approve, history
src/
  config.py            env var / Streamlit secrets loader
  db.py                 SQLite schema + persistence
  llm.py                 Gemini -> OpenAI unified provider with fallback
  research.py            Tavily web research
  prompts.py             per-platform prompt templates + response parsers
  thumbnail.py            Pillow thumbnail compositing
data/                   SQLite DB file + generated thumbnails (gitignored)
```

## Setup

1. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate        # Windows
   pip install -r requirements.txt
   ```
2. Copy `.env.example` to `.env` and fill in your API keys:
   - `GEMINI_API_KEY` — free tier at https://aistudio.google.com/apikey
   - `OPENAI_API_KEY` — fallback provider, https://platform.openai.com/api-keys
   - `TAVILY_API_KEY` — web research, https://app.tavily.com
3. Run the app:
   ```bash
   streamlit run app.py
   ```

The sidebar shows which keys are detected. Research and OpenAI fallback are optional — the app
still runs without them (with reduced functionality: no research context, no fallback on Gemini
failure).

## Testing the Gemini → OpenAI fallback

Check "Force Gemini failure (test OpenAI fallback)" in the sidebar before generating — this
forces every Gemini call to fail so you can confirm OpenAI serves the request and `provider_used`
reflects it.

## Deployment

Deploy for free on [Streamlit Community Cloud](https://streamlit.io/cloud): push this repo to
GitHub, point Streamlit Cloud at `app.py`, and set the three API keys under the app's
**Secrets** (`GEMINI_API_KEY`, `OPENAI_API_KEY`, `TAVILY_API_KEY`) — `src/config.py` reads from
`st.secrets` automatically when the equivalent env var isn't set.

## Out of scope (v1)

Auto-posting/publishing, scheduling, engagement management, published-post analytics, true
diffusion-model image generation, video generation, and multi-user auth are explicitly out of
scope for v1 — see `Social_Media_agent.docx` for the full FRD.
