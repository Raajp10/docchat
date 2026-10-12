"""Talk to any model: OpenAI, Claude, Gemini, Groq, OpenRouter, or a free local model via Ollama.

Most providers speak the OpenAI API format, so one client covers them by changing base_url.
Model names are editable in the UI — the defaults below are just starting points.
"""
from __future__ import annotations

PROVIDERS = {
    "Ollama (free, runs on your computer)": {
        "kind": "openai", "base_url": "http://localhost:11434/v1", "needs_key": False,
        "models": ["llama3.2", "qwen2.5:7b", "mistral", "gemma2"],
        "hint": "Install from ollama.com, then run:  ollama pull llama3.2",
    },
    "OpenAI": {
        "kind": "openai", "base_url": None, "needs_key": True,
        "models": ["gpt-4o-mini", "gpt-4o"],
        "hint": "Key from platform.openai.com",
    },
    "Anthropic (Claude)": {
        "kind": "anthropic", "base_url": None, "needs_key": True,
        "models": ["claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5"],
        "hint": "Key from console.anthropic.com",
    },
    "Google Gemini": {
        "kind": "openai", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "needs_key": True, "models": ["gemini-2.5-flash", "gemini-2.5-pro"],
        "hint": "Free key from aistudio.google.com",
    },
    "Groq (fast, free tier)": {
        "kind": "openai", "base_url": "https://api.groq.com/openai/v1", "needs_key": True,
        "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
        "hint": "Free key from console.groq.com",
    },
    "OpenRouter (hundreds of models)": {
        "kind": "openai", "base_url": "https://openrouter.ai/api/v1", "needs_key": True,
        "models": ["meta-llama/llama-3.3-70b-instruct:free", "anthropic/claude-sonnet-4"],
        "hint": "Key from openrouter.ai",
    },
    "No AI (search only)": {
        "kind": "none", "base_url": None, "needs_key": False, "models": ["-"],
        "hint": "Just shows the most relevant passages. Free, no setup.",
    },
}

# Simple "which model for what" guide shown in the sidebar
SUGGESTIONS = {
    "Private / sensitive documents": "Ollama — nothing leaves your computer",
    "Free and fast": "Groq or Gemini Flash (free tiers)",
    "Best accuracy on long, complex docs": "Claude Sonnet / Opus or GPT-4o",
    "Cheapest paid": "GPT-4o-mini, Claude Haiku, Gemini Flash",
}

SYSTEM_PROMPT = """You answer questions using ONLY the provided document excerpts.
Rules:
- Cite sources inline like [1], [2] matching the excerpt numbers.
- If the excerpts don't contain the answer, say "I couldn't find that in the documents." Do not guess.
- Be concise and direct."""


def build_prompt(question: str, hits) -> str:
    ctx = "\n\n".join(f"[{n}] ({c.label()})\n{c.text}" for n, (c, _) in enumerate(hits, start=1))
    return f"Document excerpts:\n\n{ctx}\n\nQuestion: {question}"


def stream_answer(provider: str, model: str, api_key: str, question: str, hits, history=None):
    """Yield the answer text piece by piece."""
    cfg = PROVIDERS[provider]
    history = history or []
    user_msg = build_prompt(question, hits)

    if cfg["kind"] == "none":
        yield "Most relevant passages are listed below under **Sources**."
        return

    if cfg["kind"] == "anthropic":
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        msgs = history + [{"role": "user", "content": user_msg}]
        with client.messages.stream(model=model, max_tokens=1500,
                                    system=SYSTEM_PROMPT, messages=msgs) as s:
            for text in s.text_stream:
                yield text
        return

    from openai import OpenAI
    client = OpenAI(api_key=api_key or "ollama", base_url=cfg["base_url"])
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}] + history + \
           [{"role": "user", "content": user_msg}]
    resp = client.chat.completions.create(model=model, messages=msgs, stream=True, temperature=0.2)
    for part in resp:
        if part.choices and part.choices[0].delta and part.choices[0].delta.content:
            yield part.choices[0].delta.content
