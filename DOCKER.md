# Running with Docker (private / self-hosted)

Use this when IEEE wants the assistant on its own infrastructure instead of
Streamlit Community Cloud — e.g. an internal VM, behind a corporate proxy, or
fronted by SSO. The same code runs in a container; you reach it at a URL on your
network.

## Prerequisites

- Docker installed on the host (and optionally Docker Compose).
- Your `ANTHROPIC_API_KEY`, and a shared `APP_PASSWORD` you choose.

## Option A — Docker Compose (recommended)

1. Create a `.env` file next to `docker-compose.yml`:

   ```env
   APP_PASSWORD=your-shared-password
   ANTHROPIC_API_KEY=sk-ant-...
   ```

2. Build and start:

   ```bash
   docker compose up -d --build
   ```

3. Open `http://<host>:8501` and enter the password.

The named volume `ieee_data` persists the built index and downloaded documents,
so restarts are fast. To refresh content later:

```bash
docker compose exec ieee-assistant python ingest.py --rebuild
```

## Option B — plain Docker

```bash
# Build the image
docker build -t ieee-section-assistant .

# Run it (pass config as environment variables)
docker run -d --name ieee-section-assistant \
  -p 8501:8501 \
  -e APP_PASSWORD="your-shared-password" \
  -e ANTHROPIC_API_KEY="sk-ant-..." \
  -v ieee_data:/app/data \
  ieee-section-assistant
```

## Configuration (environment variables)

| Variable            | Purpose                                                        |
|---------------------|----------------------------------------------------------------|
| `APP_PASSWORD`      | Shared password gate. If unset, the app is open.               |
| `ANTHROPIC_API_KEY` | Enables LLM-synthesized answers. If unset, extractive answers. |
| `OPENAI_API_KEY`    | Alternative to Anthropic (also uncomment `openai` in reqs).    |

The app reads the password from `APP_PASSWORD` (env) or `app_password`
(Streamlit secrets), and the API key from the environment — so the same image
works both self-hosted and on Streamlit Cloud.

## Putting it behind HTTPS / SSO

The container speaks plain HTTP on 8501. For production, front it with a reverse
proxy (nginx, Caddy, Traefik) that terminates TLS, and optionally place it
behind your identity provider (e.g. an OAuth2 proxy or IEEE SSO) for real
authentication instead of the shared password. Point the proxy at
`http://<container-host>:8501`.

## Notes

- **First request** builds the index (downloads public IEEE docs); it's cached
  in the volume afterward. To bake the index into the image instead, run
  `python ingest.py` before `docker build` and remove `data/index.pkl` from
  `.dockerignore`.
- **No member data** is used — only public IEEE documents — so there's nothing
  privacy-sensitive stored in the container or volume.
- **Updating the image** after code/content changes: `docker compose up -d --build`.
