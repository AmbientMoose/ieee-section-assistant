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
import hmac

import streamlit as st

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


def check_password() -> bool:
    """Gate the app behind a shared password stored in st.secrets['app_password'].
    If no password is configured, the app is open (e.g. extractive-only deploys)."""
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

for role, text in st.session_state.history:
    with st.chat_message(role):
        st.markdown(text)

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
    st.session_state.history.append(("assistant", reply))
