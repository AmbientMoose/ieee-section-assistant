# Deploying to Streamlit Community Cloud

This gives your IEEE colleagues a **URL to open** — no install required. They'll
see a password prompt, type the shared password, and use the assistant.

Total time: ~10 minutes. Cost: free hosting; you pay only for Anthropic API usage.

---

## What you need

- A **GitHub** account (free).
- A **Streamlit Community Cloud** account (free) — sign in at
  https://share.streamlit.io with your GitHub account.
- Your **Anthropic API key** (`sk-ant-...`) and a **shared password** you choose.

---

## Step 1 — Put the project on GitHub

1. Create a new repository (e.g. `ieee-section-assistant`). Private is fine —
   Streamlit Cloud can deploy private repos.
2. Upload the contents of this `ieee_assistant/` folder to the repo. You can
   drag-and-drop the files in GitHub's web UI, or use git:

   ```bash
   cd ieee_assistant
   git init
   git add .
   git commit -m "IEEE Section Operations Assistant prototype"
   git branch -M main
   git remote add origin https://github.com/<you>/ieee-section-assistant.git
   git push -u origin main
   ```

   The included `.gitignore` keeps secrets and large downloads out of the repo.

> **Faster first load (optional):** run `python ingest.py` locally first, then
> comment out the `data/index.pkl` line in `.gitignore` and commit the file.
> The server will use that prebuilt index instead of rebuilding on first boot.

## Step 2 — Create the app on Streamlit Cloud

1. Go to https://share.streamlit.io and click **Create app** → **Deploy a public
   app from GitHub** (works for private repos too).
2. Pick your repository and branch (`main`).
3. Set **Main file path** to `app.py`.
4. Click **Deploy**.

The first boot installs `requirements.txt` and, if you didn't commit an index,
builds it by downloading the public IEEE documents (this takes a couple of
minutes the first time, then it's cached).

## Step 3 — Add your secrets

1. In the app's page, open **Settings → Secrets**.
2. Paste the following (with your real values), then **Save**:

   ```toml
   app_password = "your-shared-password"
   ANTHROPIC_API_KEY = "sk-ant-..."
   ```

   See `.streamlit/secrets.toml.example` for the template. The app reads these
   automatically — `app_password` turns on the password gate, and the API key
   switches answers from extractive to LLM-synthesized. Optionally add
   `gateway_secret = "..."` (same value as in the SC2026 gateway app) to let
   signed gateway launch links skip the password prompt.
3. The app restarts automatically. Done.

## Step 4 — Share it

Send your colleagues the app URL (looks like
`https://<your-app>.streamlit.app`) and the shared password separately. They
open the link, enter the password, and start asking questions.

---

## Notes & good practices

- **Protect your API budget.** The password gate keeps random visitors from
  spending your Anthropic credits. You can also set a monthly spend limit in the
  Anthropic Console, and rotate the key if it ever leaks.
- **No member data.** This prototype uses only public IEEE documents, so there's
  no privacy-sensitive data on the server. Keep it that way for a public demo.
- **Updating content.** To pull the latest IEEE docs/KB articles, redeploy (or,
  if you committed `data/index.pkl`, run `python ingest.py --rebuild` locally and
  push the new index). The KB is auto-discovered, so new articles are picked up.
- **Turning off the LLM.** Remove `ANTHROPIC_API_KEY` from Secrets to run in
  free, extractive-only mode (it shows the top cited IEEE passages).
- **Going private/internal instead.** If IEEE needs this behind SSO or on
  internal infrastructure, the same code runs in a Docker container on any VM.
  See **DOCKER.md** for a Dockerfile, docker-compose setup, and a note on
  fronting it with HTTPS/SSO.
