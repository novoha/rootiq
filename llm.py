"""
llm.py — LLM provider abstraction for RootIQ.

Two modes, selected by `llm.mode` in mcp.json (or the Settings toggle):

  • "offline"  -> local Ollama  (http://localhost:11434, /api/chat)
  • "online"   -> any OpenAI-COMPATIBLE chat API (/chat/completions)
                  works with OpenAI, Groq, OpenRouter, Together, etc.,
                  just by changing the base_url.

SECURITY — API key handling
  The key is NEVER typed into the app UI and NEVER stored in mcp.json (that file
  is committed to git). It is resolved at call time from, in order:
      1. st.secrets["OPENAI_API_KEY"]     (Streamlit secrets — the normal path)
      2. os.environ["OPENAI_API_KEY"]     (local env var, for local runs)
  The key is used only in the Authorization header to the configured endpoint.
  It is never logged, never written to working_dir, never placed in a prompt,
  and never passed through tool arguments.
"""
import os
import requests

from config import load_config

_DEFAULT_OLLAMA = {"url": "http://localhost:11434", "model": "phi3", "timeout": 120}
_DEFAULT_ONLINE = {"base_url": "https://api.openai.com/v1",
                   "model": "gpt-4o-mini", "timeout": 120}


def llm_config() -> dict:
    """Resolve the LLM block from mcp.json, with sensible fallbacks."""
    cfg = load_config()
    llm = cfg.get("llm") or {}
    # Back-compat: an older mcp.json may only have a top-level "ollama" block.
    ollama = llm.get("ollama") or cfg.get("ollama") or _DEFAULT_OLLAMA
    online = llm.get("online") or _DEFAULT_ONLINE
    return {
        "mode": llm.get("mode", "offline"),   # "offline" | "online"
        "ollama": {**_DEFAULT_OLLAMA, **ollama},
        "online": {**_DEFAULT_ONLINE, **online},
    }


def current_mode() -> str:
    return llm_config()["mode"]


def active_model() -> str:
    c = llm_config()
    return c["online"]["model"] if c["mode"] == "online" else c["ollama"]["model"]


def provider_label() -> str:
    c = llm_config()
    if c["mode"] == "online":
        host = c["online"]["base_url"].split("//")[-1].split("/")[0]
        return f"Online · {host} · {c['online']['model']}"
    return f"Offline · Ollama · {c['ollama']['model']}"


# --------------------------------------------------------------------------- #
# API key resolution (never persisted)
# --------------------------------------------------------------------------- #
def get_api_key() -> str:
    # 1) Streamlit secrets (the normal path on Streamlit Cloud)
    try:
        import streamlit as st
        if "OPENAI_API_KEY" in st.secrets:
            return st.secrets["OPENAI_API_KEY"]
    except Exception:
        pass
    # 2) environment variable (for local runs)
    return os.environ.get("OPENAI_API_KEY", "")


def api_key_present() -> bool:
    return bool(get_api_key())


# --------------------------------------------------------------------------- #
# Health / readiness
# --------------------------------------------------------------------------- #
def llm_online() -> bool:
    """Is the active provider usable right now?"""
    c = llm_config()
    if c["mode"] == "online":
        return api_key_present()
    try:
        r = requests.get(c["ollama"]["url"], timeout=3)
        return r.status_code == 200
    except requests.RequestException:
        return False


def test_connection() -> tuple[bool, str]:
    """Active probe for the Settings 'Test connection' button."""
    c = llm_config()
    if c["mode"] == "online":
        key = get_api_key()
        if not key:
            return False, "No API key found (set OPENAI_API_KEY in Streamlit secrets)."
        try:
            r = requests.get(
                f"{c['online']['base_url'].rstrip('/')}/models",
                headers={"Authorization": f"Bearer {key}"},
                timeout=10,
            )
            if r.status_code == 200:
                return True, "Online API reachable and key accepted."
            return False, f"HTTP {r.status_code}: {r.text[:120]}"
        except requests.RequestException as e:
            return False, str(e)
    else:
        try:
            r = requests.get(c["ollama"]["url"], timeout=3)
            return (r.status_code == 200,
                    "Ollama reachable." if r.status_code == 200 else f"HTTP {r.status_code}")
        except requests.RequestException as e:
            return False, str(e)


# --------------------------------------------------------------------------- #
# Chat
# --------------------------------------------------------------------------- #
def call_llm(system: str, user: str) -> str:
    """Send a system+user turn to the active provider; return assistant text."""
    c = llm_config()
    if c["mode"] == "online":
        return _call_openai(c["online"], get_api_key(), system, user)
    return _call_ollama(c["ollama"], system, user)


def _call_ollama(cfg: dict, system: str, user: str) -> str:
    payload = {
        "model": cfg["model"],
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "stream": False,
        "options": {"temperature": 0.1},
    }
    r = requests.post(f"{cfg['url'].rstrip('/')}/api/chat",
                      json=payload, timeout=cfg.get("timeout", 120))
    r.raise_for_status()
    return r.json().get("message", {}).get("content", "")


def _call_openai(cfg: dict, key: str, system: str, user: str) -> str:
    if not key:
        raise RuntimeError("No API key configured for online mode.")
    payload = {
        "model": cfg["model"],
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "temperature": 0.1,
    }
    r = requests.post(
        f"{cfg['base_url'].rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"},
        json=payload,
        timeout=cfg.get("timeout", 120),
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]
