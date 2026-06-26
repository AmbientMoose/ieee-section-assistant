"""
Answer synthesis.

Grounded generation: the model is given ONLY the retrieved passages and asked to
answer strictly from them, with citations. If no API key is configured, the app
falls back to a transparent extractive answer (the retrieved passages verbatim),
so the prototype is fully runnable offline.
"""

import os
import re
import textwrap
from typing import List, Tuple

import config
from retriever import Chunk

SYSTEM = (
    "You are the IEEE Section Operations Assistant, a prototype that helps IEEE "
    "volunteers and officers with Section operations: training, reporting, "
    "knowledge management, membership administration (vTools, OU Analytics), and "
    "expenses (Concur).\n\n"
    "GROUNDING: Base your answer ONLY on the provided IEEE source passages, and "
    "cite each claim in brackets like [S1], [S2] matching the numbered passages. "
    "Never invent IEEE policy or numbers.\n\n"
    "ANSWER WHEN THE INFORMATION IS PRESENT. New volunteers rarely know exact "
    "IEEE terminology, so a question's wording will often differ from the "
    "wording in the passages. Treat reasonable synonyms and paraphrases as "
    "equivalent when deciding whether a passage answers the question. In "
    "particular, these are generally interchangeable: 'event(s)', 'meeting(s)', "
    "'technical meeting(s)', and 'activity/activities'; 'chapter', 'branch', "
    "'unit', and 'organizational unit (OU)'; 'geographic unit', 'geounit', and "
    "'OU'; building or creating a 'website' for a unit is done with the "
    "'WebInABox' (WIAB) tool; forming, starting, or creating a unit (e.g. a "
    "Student Branch) is covered by its 'Formation' / 'petition' procedures; "
    "'dues' and 'fees'; 'reimbursement' and 'expenses'; "
    "'officer', 'volunteer', and 'leader'. If a passage answers "
    "the question under such a reasonable reading, GIVE THE ANSWER DIRECTLY and "
    "quote the specific figure, deadline, or rule (e.g. the required number per "
    "year), with its citation. When the question asks 'how many', lead with the "
    "number.\n\n"
    "Do NOT reply that the information is missing merely because the question's "
    "wording differs from the documentation. Only say it is not in the passages "
    "when the substance is genuinely absent -- and in that case, say so plainly "
    "and suggest the volunteer check the relevant manual or contact MGA staff.\n\n"
    "GOVERNANCE vs. TOOLS: Distinguish what an IEEE governing document "
    "(Constitution, Bylaws, Policies, MGA Operations Manual) requires or "
    "authorizes from what a software tool (vTools, the Nominations Tool, OU "
    "Analytics, Concur) merely lets a user do. A help article showing that a "
    "field can be edited in a tool does NOT establish who has the authority to "
    "decide it, or what the governing rule is. For questions about authority, "
    "requirements, eligibility, or whether something is permitted or mandatory "
    "(e.g. 'can X decide', 'who decides', 'must all Y', 'is Z required'), base "
    "the answer on the governing-document passages, not on a tool's user "
    "interface. If only tool/UI passages are available, treat the governing "
    "rule as not in the passages rather than inferring it from what a screen "
    "allows.\n\n"
    "PRECISION AND NUANCE: Answer the exact question asked, and preserve "
    "qualifications, exceptions, and either/or options exactly as written. Do "
    "not convert a conditional or optional rule ('may', 'either ... or', "
    "'individually or collectively', 'recommended', 'optional') into an "
    "unconditional 'yes' or 'no'. If a rule is optional or offers alternatives, "
    "a question asking whether it is required, automatic, or applies to 'all' "
    "should usually be answered 'no', with the condition explained. State the "
    "relevant conditions rather than rounding to the simplest answer.\n\n"
    "MATCH THE EXACT ENTITY: IEEE has many similarly-named but distinct units -- "
    "a 'Chapter', a 'Student Branch', and a 'Student Branch Chapter' are "
    "different things, each with its own rules. When a passage states a "
    "requirement for the exact entity the question asks about, use that figure "
    "directly and cite it. Do NOT dismiss a stated figure just because a related "
    "entity has a different one, and do not substitute a related entity's rule "
    "for the one actually asked about.\n\n"
    "Be concise and practical."
)


def _format_passages(hits: List[Tuple[Chunk, float]]) -> str:
    blocks = []
    for i, (ch, score) in enumerate(hits, start=1):
        blocks.append(
            f"[S{i}] ({ch.doc_title}, p.{ch.page})\n{ch.text.strip()}"
        )
    return "\n\n".join(blocks)


def _source_id(i: int, url: str, markdown: bool) -> str:
    """Render a source id like [S1] - as a clickable link in markdown mode."""
    if markdown and url:
        return f"[\\[S{i}\\]]({url})"  # escaped brackets keep the [S1] text visible
    return f"[S{i}]"


def _linkify_citations(text: str, hits: List[Tuple[Chunk, float]]) -> str:
    """Turn inline [S1], [S2] references in an LLM answer into clickable links."""
    urls = {i: getattr(ch, "url", "") for i, (ch, _) in enumerate(hits, start=1)}

    def repl(m: "re.Match") -> str:
        n = int(m.group(1))
        url = urls.get(n)
        return f"[\\[S{n}\\]]({url})" if url else m.group(0)

    return re.sub(r"\[S(\d+)\]", repl, text)


def _citation_list(hits: List[Tuple[Chunk, float]], markdown: bool = False) -> str:
    lines = []
    for i, (ch, score) in enumerate(hits, start=1):
        sid = _source_id(i, getattr(ch, "url", ""), markdown)
        lines.append(f"{sid} {ch.doc_title} - p.{ch.page} (relevance {score:.2f})")
    return "\n".join(lines)


def extractive_answer(query: str, hits: List[Tuple[Chunk, float]],
                      markdown: bool = False) -> str:
    if not hits:
        return ("I couldn't find anything relevant in the indexed IEEE documents. "
                "Try rephrasing, or contact MGA staff for guidance.")
    top = hits[0][0]
    out = [
        "(No LLM key configured - showing the most relevant IEEE passages.)\n",
        f"Most relevant guidance, from {top.doc_title} (p.{top.page}):\n",
        textwrap.fill(top.text.strip(), width=88),
        "\n\nSupporting passages:",
        _citation_list(hits, markdown),
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


def synthesize(query: str, hits: List[Tuple[Chunk, float]],
               markdown: bool = False) -> str:
    """Return a grounded answer + citation list. Uses an LLM if a key exists.

    When markdown=True (web UI), source ids like [S1] - both inline in the
    answer and in the Sources list - are rendered as clickable links.
    """
    if not hits:
        return extractive_answer(query, hits, markdown)
    passages = _format_passages(hits)
    citations = "\n\nSources:\n" + _citation_list(hits, markdown)

    try:
        if os.getenv("ANTHROPIC_API_KEY"):
            answer = _anthropic(query, passages)
        elif os.getenv("OPENAI_API_KEY"):
            answer = _openai(query, passages)
        else:
            return extractive_answer(query, hits, markdown)
    except Exception as e:  # noqa: BLE001
        return (f"(LLM call failed: {e})\n\n"
                + extractive_answer(query, hits, markdown))

    if markdown:
        answer = _linkify_citations(answer, hits)
    return answer + citations
