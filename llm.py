"""
Answer synthesis.

Grounded generation: the model is given ONLY the retrieved passages and asked to
answer strictly from them, with citations. If no API key is configured, the app
falls back to a transparent extractive answer (the retrieved passages verbatim),
so the prototype is fully runnable offline.
"""

import os
import textwrap
from typing import List, Tuple

import config
from retriever import Chunk

SYSTEM = (
    "You are the IEEE Section Operations Assistant, a prototype that helps IEEE "
    "volunteers and officers with Section operations: training, reporting, "
    "knowledge management, membership administration (vTools, OU Analytics), and "
    "expenses (Concur). Answer ONLY from the provided IEEE source passages. If "
    "the passages do not contain the answer, say so plainly and suggest the "
    "volunteer contact MGA staff or check the relevant manual. Be concise and "
    "practical. After each claim, cite the source in brackets like [S1], [S2] "
    "matching the numbered passages. Never invent IEEE policy."
)


def _format_passages(hits: List[Tuple[Chunk, float]]) -> str:
    blocks = []
    for i, (ch, score) in enumerate(hits, start=1):
        blocks.append(
            f"[S{i}] ({ch.doc_title}, p.{ch.page})\n{ch.text.strip()}"
        )
    return "\n\n".join(blocks)


def _citation_list(hits: List[Tuple[Chunk, float]]) -> str:
    lines = []
    for i, (ch, score) in enumerate(hits, start=1):
        lines.append(f"[S{i}] {ch.doc_title} - p.{ch.page} (relevance {score:.2f})")
    return "\n".join(lines)


def extractive_answer(query: str, hits: List[Tuple[Chunk, float]]) -> str:
    if not hits:
        return ("I couldn't find anything relevant in the indexed IEEE documents. "
                "Try rephrasing, or contact MGA staff for guidance.")
    top = hits[0][0]
    out = [
        "(No LLM key configured - showing the most relevant IEEE passages.)\n",
        f"Most relevant guidance, from {top.doc_title} (p.{top.page}):\n",
        textwrap.fill(top.text.strip(), width=88),
        "\n\nSupporting passages:",
        _citation_list(hits),
    ]
    return "\n".join(out)


def _anthropic(query: str, passages: str) -> str:
    import anthropic
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=700,
        system=SYSTEM,
        messages=[{"role": "user",
                   "content": f"IEEE source passages:\n\n{passages}\n\n"
                              f"Question: {query}"}],
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


def _openai(query: str, passages: str) -> str:
    from openai import OpenAI
    client = OpenAI()
    resp = client.chat.completions.create(
        model=config.OPENAI_MODEL,
        max_tokens=700,
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user",
                   "content": f"IEEE source passages:\n\n{passages}\n\n"
                              f"Question: {query}"}],
    )
    return resp.choices[0].message.content


def synthesize(query: str, hits: List[Tuple[Chunk, float]]) -> str:
    """Return a grounded answer + citation list. Uses an LLM if a key exists."""
    if not hits:
        return extractive_answer(query, hits)
    passages = _format_passages(hits)
    citations = "\n\nSources:\n" + _citation_list(hits)

    try:
        if os.getenv("ANTHROPIC_API_KEY"):
            return _anthropic(query, passages) + citations
        if os.getenv("OPENAI_API_KEY"):
            return _openai(query, passages) + citations
    except Exception as e:  # noqa: BLE001
        return (f"(LLM call failed: {e})\n\n" + extractive_answer(query, hits))

    return extractive_answer(query, hits)
