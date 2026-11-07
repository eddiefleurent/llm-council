# LLM Council security model

## System overview

LLM Council is a self-hostable web app for sending a prompt to several models, collecting anonymous peer reviews, and synthesizing a final response. The intended use is for each person to clone and run the app locally, not to host it on the public internet. The repository also documents Docker Compose and Unraid deployments.

### Components

- **Browser UI** — `frontend/src/`; displays conversations and configuration, and sends prompts, attachments, and audio to the API.
- **API** — `backend/main.py`; FastAPI endpoints for conversations, model and council configuration, file extraction, and transcription; coordinates background generation.
- **LLM integrations** — `backend/council.py`, `backend/openrouter.py`, `backend/models.py`, `backend/transcription.py`; sends conversation context to OpenRouter and, when configured, audio to Groq.
- **Local persistence** — `backend/storage.py`, `backend/config.py`; stores conversation JSON and council configuration under `data/`.
- **Container deployment** — `Dockerfile`, `docker-compose.yml`, `deploy/`, `unraid/`; serves the UI and API from a container and documents host port mappings and data mounts.

## Trust boundaries and entry points

1. Browser clients reach the static UI on port 5173 and the FastAPI API on port 8001. The Docker image binds both services to all container interfaces, and Compose publishes both ports without a host-address restriction. Therefore, cloning and running the app locally does not itself guarantee loopback-only access; actual reachability depends on how each user runs it and on host/network controls.
2. The API accepts HTTP requests for conversations, model configuration, file extraction, audio transcription, and message generation. Every `/api` request requires a bearer token: `LLM_COUNCIL_API_TOKEN` from the environment, or a random token generated at startup, persisted to `data/api_token` (0600), and printed in the startup logs. CORS is restricted to the origins listed in `LLM_COUNCIL_CORS_ORIGINS` (comma-separated; defaults `http://localhost:5173` and `http://127.0.0.1:5173`; `*` is rejected). `python -m backend.main` binds `LLM_COUNCIL_HOST` (default `127.0.0.1`), and `docker-compose.yml` publishes ports on `127.0.0.1` only; LAN exposure is opt-in by changing the published ports and the origins list.
3. The LLM integrations send prompt and conversation context to OpenRouter; optional transcription sends audio to Groq. These providers are outside the app's host boundary.
4. The API reads and writes persistent JSON files on the host-mounted data directory and reads provider credentials from environment variables.

## Assets and sensitivity

The project owner treats these assets as equally important:

- Conversation prompts, responses, rankings, uploaded-file text, and transcriptions.
- OpenRouter/Groq credentials and the API usage/spend they authorize.
- Conversation and council configuration, including selected model identifiers.
- Service availability and integrity of stored conversation/configuration data.

## Attacker profiles

- **In scope:** users on a trusted private network, if a local clone's ports are reachable there; malicious prompts or attachments submitted by a client in that scope.
- **Out of scope:** public-internet-only attackers and a public internet-hosted deployment.
- Whether untrusted local processes, malicious websites accessed from the local browser, or a malicious provider/host should be in scope is not yet specified. Browser protections and host networking may affect those paths.

## Existing controls observed in code

- FastAPI/Pydantic request models validate request shapes; council model IDs are validated before saving configuration.
- Attachment extraction supports text, Markdown, PDF, JSON, and CSV; uploads are limited to 5 MiB and extracted text to 30,000 characters. Attachment content is explicitly delimited as document data in prompt context.
- Conversation paths are constrained to the data directory; conversation/config writes use temporary files and replacement.
- OpenRouter credentials are read from environment configuration; Groq is optional and initialized only when used.
- API authentication and CORS are enforced by `backend/security.py`; councils are capped at `MAX_COUNCIL_MODELS` (12) models.
- Deployment files provide a host-mounted data directory and configurable port mappings; the Compose file publishes on `127.0.0.1` by default.

## User-stated scope and accepted risk

- The intended distribution is users cloning and running the app locally, not a public internet-hosted deployment.
- Assets are equally important.
- Only users on a trusted private network are in scope; public-internet-only attackers are out of scope.
- No other accepted risks or exclusions have been stated.

## Open questions

- Are users on a private network (when LAN exposure is opted into) all equally trusted, or should some be treated as adversarial? The API token applies to all of them equally.
- Should provider-side retention/processing, malicious provider responses, and host/container compromise be included in a future revision?
