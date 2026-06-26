"""
Ingestion: download public IEEE documents (PDF + HTML), extract text, chunk, and
build the local TF-IDF index.

Run:  python ingest.py            # download (if needed) + build index
      python ingest.py --rebuild  # force re-download + rebuild

Source types (set in config.SOURCES):
  "pdf"  -> extracted page-by-page with pypdf
  "html" -> downloaded and stripped to text (vTools KB, OU Analytics, etc.)

If a download fails (offline / blocked / moved URL) the document is skipped with
a warning. A small bundled sample (sample_corpus.py) guarantees the app runs.
"""

import argparse
import re
import sys
import time
import urllib.parse as up
from html.parser import HTMLParser
from xml.etree import ElementTree as ET
from typing import List, Tuple

import requests

import config
from retriever import Chunk, build_index

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/pdf,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}
_EXT = {"pdf": ".pdf", "html": ".html"}

# An honest bot UA is the default: some IEEE hosts (mga/corporate) return HTTP
# 418 to a *spoofed* browser UA. A real browser UA is kept as a fallback for the
# rare host that blocks unknown agents instead.
_UA_PRIMARY = "IEEE-Section-Assistant/1.0 (+research prototype)"
_UA_FALLBACK = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36")

# Reuse one session so any WAF "clearance" cookie persists across requests.
_SESSION = requests.Session()
# Per-host rate limiting: stay under IEEE's WAF threshold (which returns HTTP 418
# to suspected bots). Tracks the last request time per host.
_LAST_REQUEST = {}
MIN_REQUEST_INTERVAL = float(getattr(config, "MIN_REQUEST_INTERVAL", 1.5))


def _throttle(host: str) -> None:
    wait = MIN_REQUEST_INTERVAL - (time.time() - _LAST_REQUEST.get(host, 0.0))
    if wait > 0:
        time.sleep(wait)
    _LAST_REQUEST[host] = time.time()


def _http_get(url: str, attempts: int = 3):
    """GET with several layers of resilience against IEEE's bot defenses:
      - per-host rate limiting (avoid tripping the WAF that returns HTTP 418);
      - a persistent session + same-site Referer (look less bot-like);
      - User-Agent fallback: if a host blocks with 403/418, retry with the
        other UA;
      - retry + exponential backoff for transient failures (429/5xx, timeouts).
    Other 4xx (e.g. 404) fail fast without retrying."""
    host = up.urlparse(url).netloc
    referer = f"{up.urlparse(url).scheme}://{host}/"
    last = None
    for ua in (_UA_PRIMARY, _UA_FALLBACK):
        headers = dict(HEADERS, **{"User-Agent": ua, "Referer": referer})
        for i in range(attempts):
            _throttle(host)
            try:
                r = _SESSION.get(url, headers=headers, timeout=60)
            except Exception as e:  # noqa: BLE001  (connection/timeout -> retry)
                last = e
                if i < attempts - 1:
                    time.sleep(2 ** i)
                continue
            if r.status_code in (403, 418):  # bot block -> try the other UA
                last = requests.HTTPError(f"{r.status_code} {r.reason}")
                break
            if r.status_code in (429, 500, 502, 503, 504):  # transient -> retry
                last = requests.HTTPError(f"{r.status_code} {r.reason}")
                if i < attempts - 1:
                    time.sleep(2 ** i)
                continue
            r.raise_for_status()  # other 4xx -> raise immediately (no retry)
            return r
    raise last


# --------------------------------------------------------------------------- #
# Download
# --------------------------------------------------------------------------- #
def _widen_download_url(url: str):
    """For a Widen DAM share link (.../s/<id>/<name>), return a forced-download
    variant so we get the file bytes instead of an HTML viewer page."""
    if "widen.net" not in url or "download=" in url:
        return None
    return url + ("&" if "?" in url else "?") + "download=true"


def download(source: dict):
    ext = _EXT.get(source.get("type", "pdf"), ".pdf")
    # 1) A user-provided file in data/manual/ wins and is never auto-deleted.
    #    Use this for documents the script can't fetch (e.g. Widen viewer links):
    #    download the PDF in a browser and save it as data/manual/<id>.pdf.
    manual = config.MANUAL_DIR / f"{source['id']}{ext}"
    if manual.exists() and manual.stat().st_size > 0:
        print(f"  using manual file for {source['id']}", flush=True)
        return manual
    # 2) Otherwise use the cached download if present.
    dest = config.DOCS_DIR / f"{source['id']}{ext}"
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    is_pdf = source.get("type", "pdf") == "pdf"
    try:
        print(f"  downloading {source['title']} ...", flush=True)
        content = _http_get(source["url"]).content
        # A PDF source that comes back as HTML is usually a share/landing page;
        # retry as a forced direct download (e.g. Widen ?download=true).
        if is_pdf and content[:5] != b"%PDF-":
            alt = _widen_download_url(source["url"])
            if alt:
                content = _http_get(alt).content
        if is_pdf and content[:5] != b"%PDF-":
            raise ValueError("expected a PDF but received non-PDF content "
                             "(link may be an HTML viewer; use a direct-download "
                             "URL or drop the file into data/docs/)")
        dest.write_bytes(content)
        return dest
    except Exception as e:  # noqa: BLE001
        print(f"  ! could not download {source['id']}: {e}", file=sys.stderr)
        return None


# --------------------------------------------------------------------------- #
# Extractors  ->  list of (page_number, text)
# --------------------------------------------------------------------------- #
def pdf_to_units(path) -> List[Tuple[int, str]]:
    if PdfReader is None:
        raise RuntimeError("pypdf is required: pip install pypdf")
    reader = PdfReader(str(path))
    return [(i, (p.extract_text() or "")) for i, p in enumerate(reader.pages, 1)]


class _TextExtractor(HTMLParser):
    """Collect visible text, dropping script/style/nav/header/footer content."""
    _SKIP = {"script", "style", "noscript", "head", "nav", "header", "footer", "svg"}

    def __init__(self):
        super().__init__()
        self._skip_depth = 0
        self.parts: List[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth == 0:
            text = data.strip()
            if text:
                self.parts.append(text)


# In-body boilerplate that pollutes vTools KB article text. These are plain text
# in the page body (not in <nav>/<footer> tags), so _TextExtractor can't drop
# them; left in, they dilute each chunk's tf-idf vector and hurt retrieval.
_KB_NOISE = re.compile(
    r"Skip to content"
    r"|Tip: Use arrows to navigate results, ESC to focus search input"
    r"|Click to Enlarge"
    r"|Estimated reading time:\s*\d+\s*min(?:ute)?s?",
    re.IGNORECASE,
)
# The per-article footer (feedback widget + prev/next nav) is pure chrome; drop
# everything from it onward.
_KB_FOOTER = re.compile(r"Was this article helpful\?.*$", re.IGNORECASE | re.DOTALL)


def _strip_boilerplate(text: str) -> str:
    text = _KB_FOOTER.sub(" ", text)
    text = _KB_NOISE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def html_to_units(path) -> List[Tuple[int, str]]:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    # Drop the title/content of obvious boilerplate blocks up front.
    parser = _TextExtractor()
    parser.feed(raw)
    text = " ".join(parser.parts)
    text = re.sub(r"\s+", " ", text).strip()
    text = _strip_boilerplate(text)
    return [(1, text)] if text else []


def extract(source: dict, path) -> List[Tuple[int, str]]:
    if source.get("type", "pdf") == "html":
        return html_to_units(path)
    return pdf_to_units(path)


# --------------------------------------------------------------------------- #
# vTools Knowledge Base discovery (crawl topic/index pages -> article URLs)
# --------------------------------------------------------------------------- #
class _LinkExtractor(HTMLParser):
    """Collect every href on a page."""
    def __init__(self):
        super().__init__()
        self.hrefs: List[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for k, v in attrs:
                if k == "href" and v:
                    self.hrefs.append(v.strip())


# Brand/acronym casing so auto-generated titles read correctly.
_BRAND = {
    "vtools": "vTools", "enotice": "eNotice", "enotices": "eNotices",
    "ou": "OU", "ieee": "IEEE", "webinabox": "WebInABox", "url": "URL",
    "whats": "What's", "crm": "CRM",
}
_SMALL = {"a", "an", "and", "the", "of", "to", "for", "in", "on", "your", "s"}


def _slug_to_title(slug: str) -> str:
    words = slug.replace("-", " ").strip().split()
    out = []
    for i, w in enumerate(words):
        lw = w.lower()
        if lw in _BRAND:
            out.append(_BRAND[lw])
        elif lw in _SMALL and i:
            out.append(lw)
        else:
            out.append(w.capitalize())
    return "vTools KB: " + " ".join(out)


def _fetch_text(url: str) -> str:
    """Fetch a page's text via the resilient _http_get so the crawlers (KB
    discovery, sitemaps, Volunteer Hub) get the same User-Agent fallback,
    session, rate-limiting and retry handling as file downloads."""
    return _http_get(url).text


def _urls_from_sitemaps(sitemap_urls: List[str], max_depth: int = 2) -> List[str]:
    """Walk one or more sitemaps (following <sitemapindex> entries) and return
    every <loc> URL found. Namespace-agnostic; tolerant of fetch/parse errors."""
    seen_maps = set()
    out: List[str] = []

    def walk(url: str, depth: int):
        if depth > max_depth or url in seen_maps:
            return
        seen_maps.add(url)
        try:
            xml = _fetch_text(url)
            root = ET.fromstring(xml.encode("utf-8", "ignore"))
        except Exception:  # noqa: BLE001  (missing/!xml sitemap is expected)
            return
        tag = root.tag.split("}")[-1]
        locs = [el.text.strip() for el in root.iter()
                if el.tag.split("}")[-1] == "loc" and el.text]
        if tag == "sitemapindex":
            for child in locs:
                walk(child, depth + 1)   # nested sitemaps
        else:
            out.extend(locs)             # urlset

    for u in sitemap_urls:
        walk(u, 0)
    return out


def discover_kb_articles() -> List[dict]:
    """Return a de-duplicated list of vTools KB article source dicts.

    Crawls the configured seed/index pages for article links, and always
    includes the curated known_slugs as a fallback.
    """
    cfg = getattr(config, "KB_KNOWLEDGEBASE", None)
    if not cfg or not cfg.get("enabled"):
        return []

    base = cfg["base"]
    pattern = re.compile(cfg["article_pattern"])
    found = {}  # url -> source dict

    def add_url(url: str):
        url = url.split("#")[0].split("?")[0]
        if not pattern.match(url) or url in found:
            return
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        found[url] = {
            "id": f"kb_{slug.replace('-', '_')}",
            "title": _slug_to_title(slug),
            "url": url,
            "category": cfg["category"],
            "type": "html",
        }

    # 1) curated fallback (always present)
    for slug in cfg.get("known_slugs", []):
        add_url(base + slug + "/")

    # 2) sitemap discovery (most complete; survives JS-rendered pages)
    sm_found = 0
    for loc in _urls_from_sitemaps(cfg.get("sitemaps", [])):
        before = len(found)
        add_url(loc)
        sm_found += len(found) - before
        if len(found) >= cfg.get("max_articles", 300):
            break
    if sm_found:
        print(f"  vTools KB discovery: +{sm_found} article(s) from sitemap")

    # 3) crawl seed pages ONLY if the sitemap yielded nothing (avoids redundant
    #    fetches and noisy warnings on the happy path)
    discovered = 0
    seeds = [] if sm_found else cfg.get("seeds", [])
    for seed in seeds:
        try:
            html = _fetch_text(seed)
        except Exception as e:  # noqa: BLE001
            print(f"  ! KB discovery: could not read {seed}: {e}", file=sys.stderr)
            continue
        parser = _LinkExtractor()
        parser.feed(html)
        before = len(found)
        for href in parser.hrefs:
            if href.startswith("/"):
                href = "https://kb.ieee.org" + href
            add_url(href)
        discovered += len(found) - before
        if len(found) >= cfg.get("max_articles", 300):
            break

    curated_n = len(cfg.get("known_slugs", []))
    newly = max(0, len(found) - curated_n)
    print(f"  vTools KB discovery: {len(found)} article(s) total "
          f"({curated_n} curated + {newly} discovered via sitemap/crawl)")
    return list(found.values())


# --------------------------------------------------------------------------- #
# IEEE Volunteer Hub discovery (breadth-first crawl under /volunteer-hub)
# --------------------------------------------------------------------------- #
def _hub_id(url: str, root: str) -> str:
    rel = url[len(root):].strip("/")
    rel = rel or "home"
    return "hub_" + re.sub(r"[^A-Za-z0-9]+", "_", rel).strip("_").lower()


def _titleize(segment: str) -> str:
    words = segment.replace("-", " ").replace("_", " ").split()
    out = []
    for i, w in enumerate(words):
        lw = w.lower()
        if lw in _BRAND:
            out.append(_BRAND[lw])
        elif lw in _SMALL and i:
            out.append(lw)
        else:
            out.append(w.capitalize())
    return " ".join(out)


def _hub_title(url: str, root: str) -> str:
    rel = url[len(root):].strip("/")
    if not rel:
        return "IEEE Volunteer Hub (home)"
    return "Volunteer Hub: " + _titleize(rel.rsplit("/", 1)[-1])


# Links to file assets we don't crawl/ingest as HTML pages.
_HUB_SKIP_EXT = (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
                 ".zip", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
                 ".mp4", ".mov", ".css", ".js", ".ico", ".xml", ".rss")


def discover_volunteer_hub_pages(exclude_urls=None) -> List[dict]:
    """Breadth-first crawl every page under the Volunteer Hub `root` and return
    one HTML source dict per page. Pages whose normalized URL is in `exclude_urls`
    (already listed in SOURCES) are crawled for links but not re-added as sources.

    Fetched HTML is cached into DOCS_DIR so build()'s download() reuses it
    instead of fetching each page a second time.
    """
    cfg = getattr(config, "VOLUNTEER_HUB", None)
    if not cfg or not cfg.get("enabled"):
        return []

    root = cfg["root"].rstrip("/")
    prefix = root + "/"
    parsed = up.urlparse(root)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    max_pages = cfg.get("max_pages", 250)
    delay = cfg.get("delay", 0.0)
    exclude = set(exclude_urls or ())

    def normalize(u: str) -> str:
        return u.split("#")[0].split("?")[0].rstrip("/")

    def in_scope(u: str) -> bool:
        return u == root or u.startswith(prefix)

    queue = [root]
    visited = set()
    found = {}  # normalized url -> source dict

    while queue and len(visited) < max_pages:
        url = queue.pop(0)
        nu = normalize(url)
        if nu in visited or not in_scope(nu):
            continue
        visited.add(nu)
        try:
            html = _fetch_text(url)
        except Exception as e:  # noqa: BLE001
            print(f"  ! Volunteer Hub: could not read {url}: {e}", file=sys.stderr)
            continue

        if nu not in exclude:
            sid = _hub_id(nu, root)
            found[nu] = {
                "id": sid,
                "title": _hub_title(nu, root),
                "url": nu,
                "category": cfg.get("category", "Volunteer Hub"),
                "type": "html",
            }
            # Cache page so download() won't fetch it again.
            try:
                (config.DOCS_DIR / f"{sid}.html").write_bytes(
                    html.encode("utf-8", "ignore"))
            except Exception:  # noqa: BLE001
                pass

        # enqueue in-scope links
        parser = _LinkExtractor()
        parser.feed(html)
        for href in parser.hrefs:
            if href.startswith("//"):
                href = parsed.scheme + ":" + href
            elif href.startswith("/"):
                href = origin + href
            elif not href.lower().startswith("http"):
                href = up.urljoin(url + "/", href)
            nh = normalize(href)
            if (in_scope(nh) and nh not in visited
                    and not nh.lower().endswith(_HUB_SKIP_EXT)):
                queue.append(nh)

        if delay:
            time.sleep(delay)

    print(f"  Volunteer Hub discovery: {len(found)} page(s) under {root} "
          f"({len(visited)} crawled)")
    return list(found.values())


# --------------------------------------------------------------------------- #
# Chunking
# --------------------------------------------------------------------------- #
def chunk_text(text: str, words_per: int, overlap: int) -> List[str]:
    words = text.split()
    if not words:
        return []
    chunks, start = [], 0
    step = max(1, words_per - overlap)
    while start < len(words):
        chunk = " ".join(words[start:start + words_per]).strip()
        if len(chunk) > 40:
            chunks.append(chunk)
        start += step
    return chunks


# --------------------------------------------------------------------------- #
# Build
# --------------------------------------------------------------------------- #
def print_summary(results: List[dict]) -> None:
    """Print a per-source success/skip table after a build."""
    width = max((len(r["title"]) for r in results), default=20)
    width = min(max(width, 20), 60)
    print("\n" + "=" * (width + 34))
    print("INGESTION SUMMARY")
    print("=" * (width + 34))
    print(f"  {'STATUS':<8}{'TYPE':<6}{'CHUNKS':>7}  {'SOURCE':<{width}}")
    print("  " + "-" * (width + 23))
    ok = skipped = 0
    for r in results:
        if r["status"] == "ok":
            ok += 1
            mark = "OK"
        else:
            skipped += 1
            mark = "SKIP"
        title = r["title"] if len(r["title"]) <= width else r["title"][:width - 1] + "\u2026"
        chunks = str(r["chunks"]) if r["status"] == "ok" else "-"
        print(f"  {mark:<8}{r['type']:<6}{chunks:>7}  {title:<{width}}")
        if r["status"] != "ok":
            print(f"           reason: {r['reason']}")
    print("  " + "-" * (width + 23))
    print(f"  {ok} source(s) ingested, {skipped} skipped.")
    if skipped:
        print("  Tip: fix or remove skipped URLs in config.py, then rerun "
              "`python ingest.py --rebuild`.")
    print("=" * (width + 34) + "\n")


def build() -> None:
    all_chunks: List[Chunk] = []
    cid = 0
    results: List[dict] = []

    def _norm_url(u):
        return (u or "").split("#")[0].split("?")[0].rstrip("/")

    explicit_urls = {_norm_url(s.get("url")) for s in config.SOURCES}
    sources = (list(config.SOURCES)
               + discover_kb_articles()
               + discover_volunteer_hub_pages(exclude_urls=explicit_urls))

    # De-duplicate by normalized URL (first occurrence wins, so explicit SOURCES
    # and KB articles take precedence over crawled hub pages).
    seen_urls = set()
    deduped = []
    for s in sources:
        nu = _norm_url(s.get("url"))
        if nu and nu in seen_urls:
            continue
        seen_urls.add(nu)
        deduped.append(s)
    sources = deduped

    for src in sources:
        rec = {"id": src["id"], "title": src["title"],
               "type": src.get("type", "pdf"), "status": "skip",
               "reason": "", "chunks": 0}
        path = download(src)
        if not path:
            rec["reason"] = "download failed (URL unreachable, blocked, or moved)"
            results.append(rec)
            continue
        try:
            units = extract(src, path)
        except Exception as e:  # noqa: BLE001
            print(f"  ! failed to read {src['id']}: {e}", file=sys.stderr)
            rec["reason"] = f"could not parse file: {e}"
            results.append(rec)
            continue
        if not units:
            print(f"  ! no text extracted from {src['id']} (skipped)", file=sys.stderr)
            rec["reason"] = "downloaded but no text extracted (empty or JS-rendered page)"
            results.append(rec)
            continue
        n_chunks_doc = 0
        for pno, ptext in units:
            for ck in chunk_text(ptext, config.CHUNK_WORDS, config.CHUNK_OVERLAP):
                all_chunks.append(Chunk(cid, src["id"], src["title"],
                                        src["category"], pno, ck,
                                        src.get("url", "")))
                cid += 1
                n_chunks_doc += 1
        if n_chunks_doc == 0:
            rec["reason"] = "text too short to form any chunk"
            results.append(rec)
            continue
        rec["status"] = "ok"
        rec["chunks"] = n_chunks_doc
        results.append(rec)
        print(f"  + {src['title']}: {len(units)} unit(s), {n_chunks_doc} chunks")

    any_doc = any(r["status"] == "ok" for r in results)

    # Fallback so the app always has content to demo.
    if not any_doc:
        print("No documents ingested; seeding bundled sample corpus.", file=sys.stderr)
        from sample_corpus import SAMPLE_CHUNKS
        for sc in SAMPLE_CHUNKS:
            all_chunks.append(Chunk(cid, sc["doc_id"], sc["doc_title"],
                                    sc["category"], sc["page"], sc["text"]))
            cid += 1

    if results:
        print_summary(results)

    if not all_chunks:
        print("No content available to index.", file=sys.stderr)
        sys.exit(1)

    print(f"Building index over {len(all_chunks)} chunks ...")
    index = build_index(all_chunks)
    index.save(config.INDEX_PATH)
    print(f"Index saved -> {config.INDEX_PATH}  "
          f"({index.meta['n_chunks']} chunks, {index.meta['vocab_size']} terms)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true",
                    help="force re-download and rebuild")
    args = ap.parse_args()
    if args.rebuild:
        # Clear only the auto-downloaded cache and the index. Files in
        # config.MANUAL_DIR (user-provided PDFs) are deliberately left alone.
        for f in config.DOCS_DIR.glob("*"):
            if f.is_file():
                f.unlink()
        if config.INDEX_PATH.exists():
            config.INDEX_PATH.unlink()
    build()
