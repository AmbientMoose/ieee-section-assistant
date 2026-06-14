"""
Configuration for the IEEE Section Operations AI Assistant (prototype).

SOURCES are public IEEE documents the assistant grounds its answers in. Each
source has a "type": "pdf" or "html". On first run, `ingest.py` downloads each
URL, extracts text, and builds a local search index.

NOTE: This is a proof-of-concept built on PUBLIC IEEE documents. A production
deployment would additionally require IEEE SSO / Corporate Roster authentication,
live integration with vTools / OU Analytics / Concur, ingestion of members-only
documentation, and sign-off under IEEE's generative-AI governance.
"""

from pathlib import Path

# --- Paths -------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DOCS_DIR = DATA_DIR / "docs"          # downloaded source files (pdf/html)
INDEX_PATH = DATA_DIR / "index.pkl"   # built search index
DATA_DIR.mkdir(exist_ok=True)
DOCS_DIR.mkdir(exist_ok=True)

# --- Source corpus (public IEEE documents) -----------------------------------
# type: "pdf" -> extracted page-by-page with pypdf
#       "html" -> downloaded and stripped to text (vTools KB, OU Analytics, etc.)
SOURCES = [
    # ---- Governance / Operations -------------------------------------------
    {
        "id": "mga_ops_manual_2025",
        "title": "IEEE MGA Operations Manual (2025)",
        "url": "https://mga.ieee.org/images/files/Current_MGA_Operations_Manual_2025__27_February.pdf",
        "category": "Governance / Operations",
        "type": "pdf",
    },
    {
        "id": "ieee_constitution_bylaws",
        "title": "IEEE Constitution and Bylaws",
        "url": "https://events.ieee.org/wp-content/uploads/ieee-constitution-and-bylaws.pdf",
        "category": "Governance / Operations",
        "type": "pdf",
    },
    # ---- Treasurer / Finance ------------------------------------------------
    {
        "id": "treasurer_training",
        "title": "IEEE Volunteer Training (Treasurer training & resources)",
        "url": "https://mga.ieee.org/volunteer-hub/volunteer-training",
        "category": "Treasurer / Finance",
        "type": "html",
    },
    {
        "id": "finance_operations_manual",
        "title": "IEEE Finance Operations Manual (FOM) — financial procedures",
        "url": "https://events.ieee.org/wp-content/uploads/financial-ops-manual.pdf",
        "category": "Treasurer / Finance",
        "type": "pdf",
    },
    # ---- Concur / Expenses --------------------------------------------------
    {
        "id": "travel_expense_guidelines",
        "title": "Expense Reimbursement Guidelines for IEEE Volunteers",
        "url": "https://ieee-org.widen.net/content/ztnktu9sic/pdf/travel-expense-reimbursement-guidelines.pdf?u=qhm3qm",
        "category": "Concur / Expenses",
        "type": "pdf",
    },
    {
        "id": "concur_faq",
        "title": "Concur: Frequently Asked Questions (Overview and Benefits)",
        "url": "https://corporate.ieee.org/images/files/finance/concur/frequently-asked-questions.pdf",
        "category": "Concur / Expenses",
        "type": "pdf",
    },
    # ---- vTools Knowledge Base: added automatically by the KB crawler
    #      (see KB_KNOWLEDGEBASE below). Do not list KB articles here.
    # ---- OU Analytics help (replaces SAMIEEE) -------------------------------
    {
        "id": "ou_analytics_overview",
        "title": "IEEE OU Analytics (member data tool; replaces SAMIEEE)",
        "url": "https://mga.ieee.org/volunteer-hub/volunteer-tools/ou-analytics",
        "category": "OU Analytics / Membership",
        "type": "html",
    },
    {
        "id": "ou_analytics_qa",
        "title": "IEEE OU Analytics: Questions & Answers",
        "url": "https://mga.ieee.org/volunteer-hub/volunteer-tools/ou-analytics/questions-answers",
        "category": "OU Analytics / Membership",
        "type": "html",
    },
]


# --- vTools Knowledge Base (auto-ingested) -----------------------------------
# The KB is a WordPress-style site: articles live at /vtools/blog/kb/<slug>/ and
# are grouped under topic index pages at /vtools/blog/kbtopic/<topic>/.
# `ingest.py` discovers every article by crawling the index/topic pages and
# extracting article links, then ingests each as an HTML source. If crawling is
# blocked, the curated KB_KNOWN_SLUGS below still get ingested.
KB_KNOWLEDGEBASE = {
    "enabled": True,
    "base": "https://kb.ieee.org/vtools/blog/kb/",
    "category": "vTools Knowledge Base",
    # Sitemap URLs tried first (WordPress exposes one of these). Sitemaps list
    # every article regardless of JavaScript rendering, so they are the most
    # complete discovery source; HTML crawling of "seeds" is the fallback.
    "sitemaps": [
        "https://kb.ieee.org/vtools/wp-sitemap.xml",
        "https://kb.ieee.org/vtools/sitemap_index.xml",
        "https://kb.ieee.org/vtools/sitemap.xml",
    ],
    # Pages crawled to discover article links (main index + per-tool topics):
    "seeds": [
        "https://kb.ieee.org/vtools/",
        "https://kb.ieee.org/vtools/blog/kbtopic/vtools/",
        "https://kb.ieee.org/vtools/blog/kbtopic/engage/",
        "https://kb.ieee.org/vtools/blog/kbtopic/events/",
        "https://kb.ieee.org/vtools/blog/kbtopic/enotice/",
        "https://kb.ieee.org/vtools/blog/kbtopic/officer-reporting/",
        "https://kb.ieee.org/vtools/blog/kbtopic/student-branch-reporting/",
        "https://kb.ieee.org/vtools/blog/kbtopic/voting/",
        "https://kb.ieee.org/vtools/blog/kbtopic/nominations/",
        "https://kb.ieee.org/vtools/blog/kbtopic/local-groups/",
        "https://kb.ieee.org/vtools/blog/kbtopic/webinabox/",
    ],
    # Only follow links matching this pattern (a KB article URL):
    "article_pattern": r"https://kb\.ieee\.org/vtools/blog/kb/[A-Za-z0-9][A-Za-z0-9\-]*/?$",
    "max_articles": 300,
    # Curated fallback: ingested even if discovery fails (known article slugs).
    "known_slugs": [
        "vtools-overview",
        "managing-events",
        "creating-an-event",
        "events-activity-dashboard",
        "my-events-and-manage-events-whats-the-difference",
        "pull-a-report-of-events-for-your-ou",
        "managing-enotices-using-the-enotice-dashboard",
        "sending-an-enotice-to-registrants",
        "officer-mailings",
        "a-quick-tour-of-vtools-engage",
        "vtools-officer-reporting-approvals-and-troubleshooting",
        "about-voting",
        "who-can-vote",
        "voter-instructions",
        "reporting-election-results",
    ],
}

# --- Retrieval settings ------------------------------------------------------
CHUNK_WORDS = 220
CHUNK_OVERLAP = 40
TOP_K = 5

# --- Optional LLM synthesis --------------------------------------------------
#   ANTHROPIC_API_KEY -> Anthropic (claude);  OPENAI_API_KEY -> OpenAI
ANTHROPIC_MODEL = "claude-sonnet-4-6"
OPENAI_MODEL = "gpt-4o-mini"
