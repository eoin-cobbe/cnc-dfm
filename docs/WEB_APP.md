# Web App

This repo now has a third client alongside the terminal workflow and the macOS Swift app:

- `apps/web`: Next.js frontend styled to mirror the Swift shell
- `src/dfm_web_api.py`: HTTP API that reuses the same Python analysis functions

The existing terminal and macOS app entrypoints are unchanged:

- terminal still runs through `run` and `src/dfm_cli.py`
- Swift still shells into `src/dfm_app_api.py`
- the web stack talks to `src/dfm_web_api.py`

## Architecture

The current backend design is split intentionally:

- `src/dfm_app_api.py`: machine-readable CLI for local app clients
- `src/dfm_web_api.py`: HTTP layer for browser clients and Render deployment
- `src/dfm_check.py` and related rule modules: shared analysis core

That keeps web-specific concerns such as CORS, file uploads, and artifact URLs out of the existing local client path.

## Local Run

Backend:

```bash
./.conda-env/bin/python -m pip install -r requirements-web.txt
./scripts/run-web-api.sh
```

Frontend:

```bash
cd apps/web
npm install
cp .env.example .env.local
npm run dev
```

The default browser-to-backend URL is `http://127.0.0.1:8000`.

## Render Deployment

The analysis runtime depends on `pythonocc-core`, and this repo already installs that through Conda/Mamba. Because of that, the backend is best deployed to Render as a Docker web service instead of a plain `pip install` Python service.

Files included for that flow:

- `Dockerfile.render-api`
- `requirements-web.txt`

Recommended Render backend setup:

1. Create a new Docker web service from this repo.
2. Point it at `Dockerfile.render-api`.
3. Set `CNC_DFM_WEB_ORIGINS` to your frontend origin.
4. Use `/api/v1/health` as the health check path.

## Frontend Notes

The web UI follows the same information architecture as the Swift app:

- left sidebar with `Run New Analysis`
- screens for `Recommendations`, `Rule Results`, `Analysis Summary`, `Settings`, and `Diagnostics`
- right-hand preview panel for STL geometry and overlays

The frontend uses:

- Next.js app router
- Tailwind CSS
- shadcn-style local UI primitives under `apps/web/components/ui`
- browser-side upload directly to the Python API
