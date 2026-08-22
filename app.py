"""
Streamlit chat UI for the IEEE Section Operations Assistant (prototype).

Run locally:
    pip install -r requirements.txt
    python ingest.py        # builds the index on first run
    streamlit run app.py

Deployed on Streamlit Community Cloud:
    - The index is built automatically on first boot if not committed.
    - Set ANTHROPIC_API_KEY and app_password in the app's Secrets (see DEPLOY.md).
"""

import os
import re
import hmac
import hashlib
import json
import time
import html as html_lib

import streamlit as st
import streamlit.components.v1 as components

import config
from retriever import Index
from llm import synthesize

st.set_page_config(page_title="IEEE Section Operations Assistant",
                   page_icon=":books:", layout="centered")


def _load_secrets_into_env():
    """Copy API keys from Streamlit secrets into the environment so llm.py
    (which reads os.getenv) works on Streamlit Cloud. No-op if no secrets."""
    try:
        secrets = st.secrets
    except Exception:
        return
    for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        if key in secrets and not os.getenv(key):
            os.environ[key] = str(secrets[key])


def _gateway_token_ok() -> bool:
    """Accept a signed launch token from the SC2026 gateway app
    (?gw=<expiry_unix>.<hex hmac_sha256(secret, expiry)>), so event attendees
    arriving via the gateway skip the password prompt. The shared secret lives
    in st.secrets['gateway_secret'] (or the GATEWAY_SECRET env var); with no
    secret configured, tokens are ignored and the password gate applies."""
    token = st.query_params.get("gw", "")
    if not token:
        return False
    secret = ""
    try:
        if hasattr(st, "secrets"):
            secret = str(st.secrets.get("gateway_secret", ""))
    except Exception:
        secret = ""
    if not secret:
        secret = os.getenv("GATEWAY_SECRET", "")
    if not secret:
        return False
    expiry, _, sig = token.partition(".")
    try:
        if time.time() > int(expiry):
            return False
    except ValueError:
        return False
    want = hmac.new(secret.encode(), expiry.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, want)


def check_password() -> bool:
    """Gate the app behind a shared password stored in st.secrets['app_password'].
    If no password is configured, the app is open (e.g. extractive-only deploys).
    Signed gateway launch links (see _gateway_token_ok) also pass the gate."""
    configured = ""
    try:
        if hasattr(st, "secrets"):
            configured = str(st.secrets.get("app_password", ""))
    except Exception:
        configured = ""
    # Env var fallback (used for Docker / self-hosted, which have no secrets.toml)
    if not configured:
        configured = os.getenv("APP_PASSWORD", "")
    if not configured:
        return True  # open deployment
    if st.session_state.get("auth_ok"):
        return True
    if _gateway_token_ok():
        st.session_state["auth_ok"] = True
        return True

    def _check():
        ok = hmac.compare_digest(st.session_state.get("pw", ""), configured)
        st.session_state["auth_ok"] = ok
        if ok:
            st.session_state.pop("pw", None)

    st.text_input("Enter access password", type="password", key="pw",
                  on_change=_check)
    if st.session_state.get("auth_ok") is False:
        st.error("Incorrect password. Ask Chris for the access password.")
    st.stop()


@st.cache_resource(show_spinner="Building the IEEE document index (first run only)...")
def get_index():
    if not config.INDEX_PATH.exists():
        import ingest
        ingest.build()  # downloads public IEEE docs + builds index on first boot
    if not config.INDEX_PATH.exists():
        return None
    return Index.load(config.INDEX_PATH)


_COPY_SVG = (
    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" '
    'ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 '
    '2 2v1"></path></svg>'
)
_CHECK_SVG = (
    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" '
    'stroke="#1a7f37" stroke-width="2.5" stroke-linecap="round" '
    'stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>'
)


def _basic_md_to_html(text: str) -> str:
    """Minimal Markdown -> HTML fallback (used only if the `markdown` package is
    not installed). Handles paragraphs, line breaks, bold/italic, and links
    (including the escaped-bracket [\\[S1\\]](url) citation form)."""
    blocks = []
    for para in text.split("\n\n"):
        p = html_lib.escape(para)
        p = p.replace("\\[", "[").replace("\\]", "]")        # drop md escapes
        p = re.sub(r"\[\[([^\]]+)\]\]\(([^)]+)\)",            # [[S1]](url)
                   r'<a href="\2">[\1]</a>', p)
        p = re.sub(r"\[([^\]]+)\]\(([^)]+)\)",                # [text](url)
                   r'<a href="\2">\1</a>', p)
        p = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", p)
        p = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", p)
        p = p.replace("\n", "<br>")
        blocks.append(f"<p>{p}</p>")
    return "".join(blocks)


def _md_to_html(text: str) -> str:
    """Convert Markdown to HTML so pasted answers render (bold, links) in Word."""
    try:
        import markdown as _mdlib
        return _mdlib.markdown(text, extensions=["extra", "nl2br", "sane_lists"])
    except Exception:
        return _basic_md_to_html(text)


def _embed_html(html: str, height: int) -> None:
    """Render an HTML+JS snippet in an iframe, using whichever API the installed
    Streamlit provides: st.iframe (>=1.56) or the deprecated components.html."""
    html = html.strip()  # ensure it's detected as inline HTML, not a URL/path
    if hasattr(st, "iframe"):
        st.iframe(html, height=height)
    else:
        components.html(html, height=height)


def render_copy_button(question: str, answer: str, key: str) -> None:
    """Render a single copy icon that copies the question + answer (including
    hyperlinks) to the clipboard as RICH TEXT, so pasting into Word/Docs renders
    the formatting instead of showing Markdown codes. Shows a checkmark on copy."""
    body_html = _md_to_html(f"**Question:** {question}\n\n{answer}")
    payload = json.dumps(body_html).replace("</", "<\\/")  # safe inside <script>
    html = f"""
    <button id="b{key}" title="Copy question and answer (formatted)"
      style="background:none;border:none;cursor:pointer;padding:4px;margin:0;
             color:#5f6368;display:inline-flex;align-items:center;border-radius:6px;"
      onmouseover="this.style.background='#f0f2f6'"
      onmouseout="this.style.background='none'">
      <span id="i{key}">{_COPY_SVG}</span>
    </button>
    <script>
      (function() {{
        const btn = document.getElementById("b{key}");
        const ic = document.getElementById("i{key}");
        const htmlContent = {payload};
        const COPY = {json.dumps(_COPY_SVG)};
        const CHECK = {json.dumps(_CHECK_SVG)};
        btn.addEventListener("click", function() {{
          // Copy rendered HTML by selecting a contenteditable node; this puts
          // both text/html and text/plain on the clipboard, so Word renders it.
          const div = document.createElement("div");
          div.setAttribute("contenteditable", "true");
          div.innerHTML = htmlContent;
          div.style.position = "fixed"; div.style.left = "-9999px";
          div.style.top = "0"; div.style.whiteSpace = "normal";
          document.body.appendChild(div);
          const range = document.createRange();
          range.selectNodeContents(div);
          const sel = window.getSelection();
          sel.removeAllRanges(); sel.addRange(range);
          let ok = false;
          try {{ ok = document.execCommand("copy"); }} catch (e) {{ ok = false; }}
          sel.removeAllRanges();
          document.body.removeChild(div);
          ic.innerHTML = CHECK;
          setTimeout(function() {{ ic.innerHTML = COPY; }}, 1500);
        }});
      }})();
    </script>
    """
    _embed_html(html, 36)


_load_secrets_into_env()
check_password()


EXAMPLES = [
    "I'm a new Section Treasurer - what reporting am I responsible for?",
    "What are the Concur expense rules? Do I need receipts?",
    "How do I report new officers in vTools?",
    "What is OU Analytics and who can use it?",
    "Which vTools application do I use to send a meeting notice?",
]

st.title("IEEE Section Operations Assistant")
st.caption("Prototype - grounded in public IEEE documents. Every answer cites its sources.")

index = get_index()
if index is None:
    st.error("Could not build or load the document index. Check the app logs; "
             "the bundled sample corpus should normally guarantee content.")
    st.stop()

with st.sidebar:
    st.subheader("Indexed sources")
    seen = {}
    for ch in index.chunks:
        seen.setdefault(ch.doc_title, (ch.category, getattr(ch, "url", "")))
    for title, (cat, url) in seen.items():
        label = f"[{title}]({url})" if url else title
        st.markdown(f"- **{label}**  \n  _{cat}_")
    st.divider()
    st.caption(f"{index.meta['n_chunks']} passages indexed.")
    st.caption("Set ANTHROPIC_API_KEY or OPENAI_API_KEY for synthesized "
               "answers; otherwise the app shows the top source passages.")
    st.divider()
    st.markdown("**Prototype scope:** public docs only. Production would add IEEE "
                "SSO, role-aware access via the Corporate Roster, and live vTools / "
                "OU Analytics / Concur integration.")

if "history" not in st.session_state:
    st.session_state.history = []

st.write("**Try an example:**")
cols = st.columns(2)
for i, ex in enumerate(EXAMPLES):
    if cols[i % 2].button(ex, key=f"ex{i}", use_container_width=True):
        st.session_state.pending = ex

for idx, (role, text) in enumerate(st.session_state.history):
    with st.chat_message(role):
        st.markdown(text)
        if role == "assistant":
            q = st.session_state.history[idx - 1][1] if idx > 0 else ""
            render_copy_button(q, text, key=f"hist{idx}")

prompt = st.chat_input("Ask about Section operations, reporting, vTools, Concur...")
if "pending" in st.session_state and not prompt:
    prompt = st.session_state.pop("pending")

if prompt:
    st.session_state.history.append(("user", prompt))
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Searching IEEE documents..."):
            hits = index.search(prompt, top_k=config.TOP_K)
            reply = synthesize(prompt, hits, markdown=True)
        st.markdown(reply)
        if hits:
            with st.expander("Show retrieved passages"):
                for i, (ch, score) in enumerate(hits, start=1):
                    url = getattr(ch, "url", "")
                    sid = f"[\\[S{i}\\]]({url})" if url else f"[S{i}]"
                    st.markdown(f"**{sid} {ch.doc_title} - p.{ch.page}** "
                                f"(relevance {score:.2f})")
                    st.write(ch.text.strip())
        render_copy_button(prompt, reply, key="live")
    st.session_state.history.append(("assistant", reply))
