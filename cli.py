"""Command-line DocChat.

  python cli.py ./my-folder                          # search only, no AI
  python cli.py ./my-folder --provider ollama --model llama3.2
  python cli.py ./my-folder --provider openai --model gpt-4o-mini   (uses OPENAI_API_KEY)
  python cli.py ./my-folder --ask "What is the refund policy?"
  python cli.py ./my-folder --rebuild                 # re-read files after changes
"""
import argparse
import os
import sys

from docchat.index import Index
from docchat.ingest import load_folder
from docchat.providers import PROVIDERS, stream_answer

SHORT = {"ollama": "Ollama (free, runs on your computer)", "openai": "OpenAI",
         "claude": "Anthropic (Claude)", "anthropic": "Anthropic (Claude)",
         "gemini": "Google Gemini", "groq": "Groq (fast, free tier)",
         "openrouter": "OpenRouter (hundreds of models)", "none": "No AI (search only)"}
ENV = {"OpenAI": "OPENAI_API_KEY", "Anthropic (Claude)": "ANTHROPIC_API_KEY",
       "Google Gemini": "GEMINI_API_KEY", "Groq (fast, free tier)": "GROQ_API_KEY",
       "OpenRouter (hundreds of models)": "OPENROUTER_API_KEY"}


def main():
    ap = argparse.ArgumentParser(description="Chat with a folder of documents.")
    ap.add_argument("folder")
    ap.add_argument("--provider", default="none", choices=sorted(SHORT))
    ap.add_argument("--model", default=None)
    ap.add_argument("--ask", default=None, help="Ask one question and exit")
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("-k", type=int, default=6)
    a = ap.parse_args()

    if not os.path.isdir(a.folder):
        sys.exit(f"Folder not found: {a.folder}")
    provider = SHORT[a.provider]
    model = a.model or PROVIDERS[provider]["models"][0]
    key = os.environ.get(ENV.get(provider, ""), "")
    if PROVIDERS[provider]["needs_key"] and not key:
        sys.exit(f"Set {ENV[provider]} first.")

    idx = None if a.rebuild else Index.load(a.folder)
    if idx is None:
        chunks, errors = load_folder(a.folder, lambda i, n, f: print(f"  reading {f}"))
        for e in errors:
            print("  skipped", e)
        idx = Index.build(chunks)
        idx.save(a.folder)
    print(f"{len({c.source for c in idx.chunks})} files, {len(idx.chunks)} passages, "
          f"search: {idx.mode}, model: {provider} / {model}\n")

    def answer(q):
        hits = idx.search(q, k=a.k)
        if not hits:
            print("Nothing related found.\n")
            return
        for piece in stream_answer(provider, model, key, q, hits):
            print(piece, end="", flush=True)
        print("\n\nSources:")
        for n, (c, _) in enumerate(hits, 1):
            print(f"  [{n}] {c.label()}: {c.text[:120].replace(chr(10), ' ')}…")
        print()

    if a.ask:
        answer(a.ask)
        return
    while True:
        try:
            q = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if q in {"exit", "quit"}:
            break
        if q:
            answer(q)


if __name__ == "__main__":
    main()
