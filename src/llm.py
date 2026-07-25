import logging

from src.config import get_secret

logger = logging.getLogger(__name__)

# Toggled from the Streamlit sidebar to demo the Gemini -> Groq fallback path
# (FRD success criterion: "Gemini->fallback demonstrably works").
_force_gemini_failure = False


class LLMError(Exception):
    pass


def set_force_gemini_failure(flag: bool) -> None:
    global _force_gemini_failure
    _force_gemini_failure = flag


def _call_gemini(prompt: str) -> str:
    if _force_gemini_failure:
        raise LLMError("Gemini call disabled (force-failure test mode is on)")

    api_key = get_secret("GEMINI_API_KEY")
    if not api_key:
        raise LLMError("GEMINI_API_KEY not configured")

    import google.generativeai as genai

    genai.configure(api_key=api_key)
    model_name = get_secret("GEMINI_MODEL", "gemini-2.0-flash")
    model = genai.GenerativeModel(model_name)
    response = model.generate_content(prompt)

    text = getattr(response, "text", None)
    if not text:
        raise LLMError("Gemini returned an empty response")
    return text.strip()


def _call_groq(prompt: str) -> str:
    api_key = get_secret("GROQ_API_KEY")
    if not api_key:
        raise LLMError("GROQ_API_KEY not configured")

    from groq import Groq

    client = Groq(api_key=api_key)
    model_name = get_secret("GROQ_MODEL", "llama-3.3-70b-versatile")
    response = client.chat.completions.create(
        model=model_name,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.choices[0].message.content
    if not text:
        raise LLMError("Groq returned an empty response")
    return text.strip()


def generate_content(prompt: str, platform: str = "") -> dict:
    """Unified generation entry point used by every platform's prompt template.

    Tries Gemini first (free tier); on any failure (rate limit, timeout, missing
    key, etc.) falls back to Groq. Returns a normalized dict regardless of
    which provider actually served the request.
    """
    try:
        text = _call_gemini(prompt)
        return {"text": text, "provider_used": "gemini", "error": None}
    except Exception as gemini_error:
        logger.warning("Gemini failed for platform=%s: %s", platform, gemini_error)
        try:
            text = _call_groq(prompt)
            return {"text": text, "provider_used": "groq", "error": None}
        except Exception as groq_error:
            logger.error("Groq fallback also failed for platform=%s: %s", platform, groq_error)
            raise LLMError(
                f"Both providers failed for {platform or 'generation'}. "
                f"Gemini: {gemini_error} | Groq: {groq_error}"
            )
