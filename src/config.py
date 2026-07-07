import os

from dotenv import load_dotenv

load_dotenv()


def get_secret(key: str, default=None):
    """Read a config value from the environment first, then Streamlit secrets
    (for Streamlit Community Cloud deployments where env vars aren't set)."""
    val = os.environ.get(key)
    if val:
        return val
    try:
        import streamlit as st

        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return default
