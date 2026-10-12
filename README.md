# DocChat

Chat with your own documents using any AI model. Every answer shows which file and page it came from.

- **Any documents:** PDF, Word (.docx), text, Markdown, CSV, including subfolders
- **Any model:** OpenAI, Claude, Gemini, Groq, OpenRouter, or **free local models with Ollama**
- **Private:** files stay on your computer. With Ollama, nothing leaves it at all.
- **Free search mode:** "No AI" shows the most relevant passages with zero setup

## Start (one click)

You need Python 3.10 to 3.13 (3.14 is too new for the search library; `start.sh` / `start.bat` pick a compatible version automatically).

- **Mac / Linux:** double-click `start.sh` (or run `./start.sh`)
- **Windows:** double-click `start.bat`

The first run installs everything (a few minutes). After that the app opens in your browser at `http://localhost:8501`.

Manual way:
```bash
pip install -r requirements.txt
streamlit run app.py
```

## How to use

1. **Add documents:** type a folder path and click **Load**, or use the **Upload files** tab.
2. **Pick a model** in the sidebar and paste your API key (or choose Ollama / No AI).
3. **Ask questions.** Open **Sources** under any answer to see the exact passages used.

Added or changed files? Click **Rebuild**.

## Free local model (Ollama)

1. Install from https://ollama.com
2. Run `ollama pull llama3.2`
3. Pick **Ollama** in the app. No key needed.

## Which model should I use?

| Need | Pick |
|---|---|
| Private / sensitive documents | Ollama (runs on your computer) |
| Free and fast | Groq or Gemini Flash (free tiers) |
| Best accuracy on long, complex docs | Claude Sonnet / Opus or GPT-4o |
| Cheapest paid | GPT-4o-mini, Claude Haiku, Gemini Flash |

Any model name can be typed in via **Model → Other…**

## API keys

Paste them in the sidebar, or set environment variables so they fill in automatically:
`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`.
Keys are only sent to the provider you choose.

## Command line

```bash
python cli.py ./my-folder                                    # search only
python cli.py ./my-folder --provider ollama --model llama3.2
python cli.py ./my-folder --provider openai --ask "What is the refund policy?"
python cli.py ./my-folder --rebuild                          # after changing files
```

## How it works

```
folder ──► read files ──► split into passages ──► search index (saved in <folder>/.docchat/)
                                                        │
question ──► find best 6 passages (keywords + meaning) ─┘──► AI model ──► answer + [1][2] sources
```

- **Search** combines keyword matching (BM25) with meaning matching (a small free embedding model, downloaded once, ~130 MB). If the model can't download, it falls back to keywords only. Set `DOCCHAT_KEYWORD_ONLY=1` to force keyword-only.
- The AI is told to answer **only** from the passages and to say "I couldn't find that" instead of guessing.

## Files

```
app.py                 web app (Streamlit)
cli.py                 command-line version
docchat/ingest.py      reads PDF/Word/text files, splits into passages
docchat/index.py       hybrid search index
docchat/providers.py   all model providers + prompt
```

## Limits (version 1)

- Scanned PDFs (images of text) need OCR first. Text-based PDFs work.
- Built for hundreds to a few thousand pages. Larger collections need a vector database.
- Single user, runs locally. Not a hosted multi-user service.
