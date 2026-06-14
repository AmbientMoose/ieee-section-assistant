# IEEE Section Operations Assistant — Prototype

A runnable proof-of-concept of the "IEEE AI assistant" described in the
Sections Congress recommendation *AI-Driven Digital Transformation for IEEE
Section Operations*. It is a **retrieval-augmented (RAG) assistant** that answers
volunteer/officer questions about Section operations — training, reporting,
knowledge management, membership administration, and Concur expenses — using
**only** IEEE's own published documents, and **cites its sources** for every answer.

This demonstrates the concept end-to-end on **public** IEEE documents. It is not
the production system (see *Prototype vs. production* below).

## What it does

1. **Ingests** public IEEE documents (PDF + HTML — see `config.py`): the MGA
   Operations Manual, volunteer expense reimbursement guidelines and Concur FAQ,
   the **vTools Knowledge Base** articles, and the **OU Analytics** help pages
   (OU Analytics is IEEE's member-data tool that replaced SAMIEEE).
   The **entire vTools Knowledge Base is auto-discovered**: `ingest.py` first
   parses the KB **sitemap** (most complete, survives JS-rendered pages) and
   falls back to crawling the KB topic/index pages, extracting every article
   link and ingesting each — with a curated list as a final fallback if both are
   blocked. Configure it via `KB_KNOWLEDGEBASE` in `config.py`.
2. **Indexes** them into a local TF-IDF search index (pure `numpy`, no heavy ML
   dependencies, runs anywhere).
3. **Answers** a natural-language question by retrieving the most relevant
   passages and synthesizing a grounded, cited reply.

If an `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` is set, answers are written by an
LLM constrained to the retrieved passages. With **no key**, the app falls back to
a transparent extractive answer (it shows the most relevant passages). Either
way it runs.

## Quick start

```bash
cd ieee_assistant
pip install -r requirements.txt

python ingest.py            # downloads public PDFs + builds the index
# (offline? it auto-seeds a small bundled sample so the demo still works)

# Option A — web chat UI:
streamlit run app.py

# Option B — terminal:
python cli.py
python cli.py "What are the Concur expense rules?"
```

Optional, for synthesized answers:

```bash
export ANTHROPIC_API_KEY=sk-...   # or OPENAI_API_KEY=sk-...
pip install anthropic             # or: pip install openai
```

## Files

| File | Purpose |
|------|---------|
| `config.py` | Source document list + settings |
| `ingest.py` | Download PDFs, extract text, chunk, build index |
| `retriever.py` | TF-IDF index + cosine-similarity search |
| `llm.py` | Grounded answer synthesis (LLM or extractive fallback) |
| `app.py` | Streamlit chat UI with citations |
| `cli.py` | Command-line interface |
| `sample_corpus.py` | Bundled offline fallback content |

## Example questions

- "I'm a new Section Treasurer — what reporting am I responsible for?"
- "What are the Concur expense rules? Do I need receipts?"
- "How do I report new officers in vTools?"
- "What is OU Analytics and who can use it?"

## Prototype vs. production

This prototype covers the *technical core* (grounded retrieval + citations). A
real IEEE deployment additionally requires, and is **out of scope** here:

- **IEEE SSO / Corporate Roster** authentication and **role-aware** access
  (a Treasurer vs. a Student Branch Counselor see different guidance/data).
- **Live integration** with vTools, OU Analytics, and Concur APIs (this demo reads
  documentation; it does not transact).
- Ingestion of **members-only** documentation and a pipeline that tracks each
  new manual edition.
- Review under **IEEE's generative-AI governance**, plus member-data privacy
  controls.

## Note on sources

Documents are IEEE's own public PDFs, downloaded at runtime from ieee.org. The
bundled `sample_corpus.py` paraphrases public IEEE guidance for offline demo use
only. This project is an independent prototype and is not affiliated with or
endorsed by IEEE.
