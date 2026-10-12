"""DocChat — chat with your own documents, using any AI model.

Run:  streamlit run app.py
"""
import os
import re

import streamlit as st

from docchat.index import Index
from docchat.ingest import load_folder
from docchat.providers import PROVIDERS, SUGGESTIONS, stream_answer

st.set_page_config(page_title="DocChat", page_icon="📄", layout="wide")
UPLOAD_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "workspaces")
ENV_KEYS = {"OpenAI": "OPENAI_API_KEY", "Anthropic (Claude)": "ANTHROPIC_API_KEY",
            "Google Gemini": "GEMINI_API_KEY", "Groq (fast, free tier)": "GROQ_API_KEY",
            "OpenRouter (hundreds of models)": "OPENROUTER_API_KEY"}

ss = st.session_state
ss.setdefault("index", None)
ss.setdefault("folder", "")
ss.setdefault("messages", [])


def build(folder: str, force: bool = False):
    if not force:
        cached = Index.load(folder)
        if cached:
            ss.index, ss.folder = cached, folder
            return
    bar = st.sidebar.progress(0.0, text="Reading files…")
    chunks, errors = load_folder(
        folder, progress=lambda i, n, f: bar.progress(i / max(n, 1), text=f"Reading {f}"))
    bar.progress(1.0, text="Building search index…")
    idx = Index.build(chunks)
    idx.save(folder)
    bar.empty()
    ss.index, ss.folder, ss.messages = idx, folder, []
    for e in errors:
        st.sidebar.warning(f"Skipped {e}")


# ---------------- Sidebar ----------------
with st.sidebar:
    st.title("📄 DocChat")

    st.subheader("1. Your documents")
    tab_folder, tab_upload = st.tabs(["Folder on this computer", "Upload files"])
    with tab_folder:
        folder = st.text_input("Folder path", value=ss.folder,
                               placeholder="/Users/you/Documents/company-docs")
        c1, c2 = st.columns(2)
        if c1.button("Load", use_container_width=True, disabled=not folder):
            if os.path.isdir(folder):
                build(folder)
            else:
                st.error("Folder not found.")
        if c2.button("Rebuild", use_container_width=True, disabled=not folder,
                     help="Re-read all files (use after adding/changing documents)"):
            if os.path.isdir(folder):
                build(folder, force=True)
    with tab_upload:
        name = st.text_input("Project name", value="my-docs")
        files = st.file_uploader("PDF, Word, text, markdown, CSV", accept_multiple_files=True,
                                 type=["pdf", "docx", "txt", "md", "csv"])
        if st.button("Add & index", use_container_width=True, disabled=not files):
            target = os.path.join(UPLOAD_ROOT, name.strip() or "my-docs")
            os.makedirs(target, exist_ok=True)
            for f in files:
                with open(os.path.join(target, f.name), "wb") as out:
                    out.write(f.getbuffer())
            build(target, force=True)

    if ss.index:
        n_files = len({c.source for c in ss.index.chunks})
        st.success(f"{n_files} files · {len(ss.index.chunks)} passages\n\nSearch: {ss.index.mode}")

    st.subheader("2. AI model")
    provider = st.selectbox("Provider", list(PROVIDERS))
    cfg = PROVIDERS[provider]
    st.caption(cfg["hint"])
    if cfg["kind"] != "none":
        model = st.selectbox("Model", cfg["models"] + ["Other…"])
        if model == "Other…":
            model = st.text_input("Model name")
    else:
        model = "-"
    api_key = ""
    if cfg["needs_key"]:
        api_key = st.text_input("API key", type="password",
                                value=os.environ.get(ENV_KEYS.get(provider, ""), ""),
                                help="Stays on your computer. Only sent to the provider you picked.")

    with st.expander("Which model should I use?"):
        for need, pick in SUGGESTIONS.items():
            st.markdown(f"**{need}:** {pick}")

    k = st.slider("Passages per answer", 3, 12, 6)
    if st.button("Clear chat"):
        ss.messages = []

# ---------------- Chat ----------------
if not ss.index:
    st.markdown("## Chat with your documents")
    st.markdown("1. Pick a folder or upload files on the left.\n"
                "2. Choose an AI model (or a free local one).\n"
                "3. Ask questions — every answer shows which file and page it came from.")
    st.stop()


def plain(text: str) -> str:
    """Show document text as-is: escape markdown so '# Pricing' isn't a heading or '$89 … $149' math."""
    return re.sub(r"([\\`*_{}\[\]<>()#+\-.!|$~])", r"\\\1", text)


def no_math(text: str) -> str:
    """Keep the AI's formatting, but stop dollar amounts from rendering as math."""
    return text.replace("$", "\\$")


def show_sources(hits):
    with st.expander(f"Sources ({len(hits)})"):
        for n, h in enumerate(hits, start=1):
            st.markdown(f"**[{n}] {h['label']}**")
            st.caption(plain(h["text"][:700]) + ("…" if len(h["text"]) > 700 else ""))


for m in ss.messages:
    with st.chat_message(m["role"]):
        st.markdown(no_math(m["content"]))
        if m.get("sources"):
            show_sources(m["sources"])

if q := st.chat_input("Ask about your documents…"):
    ss.messages.append({"role": "user", "content": q})
    with st.chat_message("user"):
        st.markdown(no_math(q))

    hits = ss.index.search(q, k=k)
    sources = [{"label": c.label(), "text": c.text} for c, _ in hits]
    history = [{"role": m["role"], "content": m["content"]} for m in ss.messages[:-1]][-6:]

    with st.chat_message("assistant"):
        if not hits:
            answer = "I couldn't find anything related in the documents."
            st.markdown(answer)
        elif cfg["needs_key"] and not api_key:
            answer = "Add your API key in the sidebar (or pick Ollama / No AI)."
            st.warning(answer)
        else:
            try:
                answer = st.write_stream(
                    no_math(t) for t in stream_answer(provider, model, api_key, q, hits, history))
                answer = answer.replace("\\$", "$")
            except Exception as e:
                answer = f"Model error: {e}"
                st.error(answer)
                if "Ollama" in provider:
                    st.info("Is Ollama running? Start it and run `ollama pull " + model + "`.")
        show_sources(sources)
    ss.messages.append({"role": "assistant", "content": answer, "sources": sources})
