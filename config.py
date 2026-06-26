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
DOCS_DIR = DATA_DIR / "docs"          # auto-downloaded cache (wiped by --rebuild)
MANUAL_DIR = DATA_DIR / "manual"      # user-provided files; NEVER auto-deleted
INDEX_PATH = DATA_DIR / "index.pkl"   # built search index
DATA_DIR.mkdir(exist_ok=True)
DOCS_DIR.mkdir(exist_ok=True)
MANUAL_DIR.mkdir(exist_ok=True)

# --- Source corpus (public IEEE documents) -----------------------------------
# type: "pdf" -> extracted page-by-page with pypdf
#       "html" -> downloaded and stripped to text (vTools KB, OU Analytics, etc.)
SOURCES = [
    # ---- Governance / Operations -------------------------------------------
    {
        "id": "mga_ops_manual_2026",
        "title": "IEEE MGA Operations Manual (2026)",
        "url": "https://mga.ieee.org/images/files/board-committees/Ops%20Manual/Current%20MGA%20Operations%20Manual%202026_23%20February%202026.pdf",
        "category": "Governance / Operations",
        "type": "pdf",
    },
    {
        "id": "ieee_constitution_bylaws",
        "title": "IEEE Constitution and Bylaws",
        "url": "https://ieee-org.widen.net/s/xcmfjhtrv2/ieee-constitution-and-bylaws",
        "category": "Governance / Operations",
        "type": "pdf",
    },
    {
        "id": "ieee_policies",
        "title": "IEEE Policies",
        "url": "https://www.ieee.org/content/dam/ieee-org/ieee/web/org/about/whatis/ieee-policies.pdf",
        "category": "Governance / Operations",
        "type": "pdf",
    },
    {
        "id": "ieee_certificate_of_incorporation",
        "title": "IEEE Certificate of Incorporation",
        "url": "https://ieee-org.widen.net/s/5tfbmnw6pq/01-05-1993_certificate_of_incorporation",
        "category": "Governance / Operations",
        "type": "pdf",
    },
    {
        "id": "nac_operations_manual",
        "title": "IEEE Nominations & Appointments Committee (N&A) Operations Manual",
        # Widen viewer link (pdf.js) -- not directly downloadable by the script;
        # download in a browser and drop into data/docs/nac_operations_manual.pdf
        "url": "https://ieee-org.widen.net/s/rzfzk8nmxz/nac-ops-manual",
        "category": "Governance / Operations",
        "type": "pdf",
    },
    {
        "id": "ieee_investment_operations_manual",
        "title": "IEEE Investment Operations Manual (IOM)",
        "url": "https://ieee-org.widen.net/s/xmpwxxkjmx/ieee-investment-operations-manual",
        "category": "Governance / Operations",
        "type": "pdf",
    },
    # Also suggested by A. Luque for completeness (add a URL to ingest if wanted):
    #   New York Not-for-Profit Corporation Law (NPCL) -- external NY State statute,
    #   large; host or link a PDF and add an entry here to include it.
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
        "url": "https://ieee-org.widen.net/s/6nqd2dfrd6/financial-ops-manual",
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
        "title": "Concur: Frequently Asked Questions",
        "url": "https://corporate.ieee.org/images/files/finance/concur/Concur_FAQs.pdf",
        "category": "Concur / Expenses",
        "type": "pdf",
    },
    {
        "id": "ieee_expense_report",
        "title": "IEEE Expense Report — NextGen Expense (Concur): how to get reimbursed",
        "url": "https://corporate.ieee.org/resources/travel-medical-and-insurance/ieee-expense-report",
        "category": "Concur / Expenses",
        "type": "html",
        # This page is JavaScript-rendered (a plain fetch returns nothing), so its
        # text is captured in data/manual/ieee_expense_report.html to guarantee
        # ingestion. The downloader prefers that manual file over fetching.
    },
    {
        "id": "nextgen_expense_checklist",
        "title": "NextGen Expense Reimbursement Checklist (getting started & submitting)",
        "url": "https://corporate.ieee.org/images/files/finance/concur/NextGenExpenseReimb_Checklist_7feb2021.pdf",
        "category": "Concur / Expenses",
        "type": "pdf",
    },
    {
        "id": "concur_exceptions_icons",
        "title": "Concur: Exception Icons & Definitions (Travel & Expense)",
        "url": "https://corporate.ieee.org/images/files/finance/concur/exception-icons-and-definitions-travel-and-expense.pdf",
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
        "intro-to-webinabox",
        "local-groups-overview",
        "how-to-request-a-local-group",
    ],
}

# --- IEEE Volunteer Hub (auto-ingested by crawling) --------------------------
# Starting at `root`, ingest.py crawls every page whose URL stays under that
# path (e.g. /volunteer-hub/geographic-unit-operations/...), following internal
# links breadth-first. Each HTML page becomes a source. Pages already listed in
# SOURCES (e.g. volunteer-training, ou-analytics) are de-duplicated automatically.
VOLUNTEER_HUB = {
    "enabled": True,
    "root": "https://mga.ieee.org/volunteer-hub",
    "category": "Volunteer Hub",
    "max_pages": 250,        # safety cap on how many pages to crawl
    "delay": 0.3,            # seconds between fetches (be polite to IEEE servers)
}

# --- Retrieval settings ------------------------------------------------------
CHUNK_WORDS = 220
CHUNK_OVERLAP = 40
TOP_K = 8

# --- Optional LLM synthesis --------------------------------------------------
#   ANTHROPIC_API_KEY -> Anthropic (claude);  OPENAI_API_KEY -> OpenAI
ANTHROPIC_MODEL = "claude-opus-4-8"
OPENAI_MODEL = "gpt-4o-mini"
