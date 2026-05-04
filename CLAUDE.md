# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BGP Huawei Automation Tool — a full-stack NOC tool for automating BGP session provisioning on Huawei NE8000 routers (NE8000-F1A/M4). It consists of three layers:

1. **`backend/bgp/`** — core business logic: command generation, IRR/RADB validation, SSH execution, PDF report generation
2. **`backend/api/`** — FastAPI REST backend exposing the `bgp/` logic, with JWT authentication
3. **`frontend/`** — React 18 + Vite SPA for the web interface

`backend/main.py` is the original interactive CLI entry point (still functional). `backend/script.py` is the original monolithic version kept for reference only.

**Always `cd backend` before running Python commands** — relative paths in `config.py` (`routers.txt`, `backups/`, `logs/`) resolve from the working directory.

## Commands

```powershell
# Install Python dependencies
cd backend
pip install -r requirements.txt

# Run the API server (port 8000) — always run from inside backend/
cd backend
python api_main.py
# Swagger UI available at http://localhost:8000/docs

# Run the interactive CLI (original)
cd backend
python main.py

# Run the React frontend (port 5173, dev mode)
cd frontend
npm install   # first time only
npm run dev

# Build frontend for production
cd frontend
npm run build
```

### First-time .env setup (required for the API)
```powershell
# Generate bcrypt hash for your password
cd backend
python -c "import bcrypt; print(bcrypt.hashpw(b'your_password', bcrypt.gensalt()).decode())"
```
Create `backend/.env` (already in `.gitignore`):
```
JWT_SECRET=<random long string>
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=<hash from above>
JWT_EXPIRE_HOURS=8
```

## Architecture

### `bgp/` — Core library (no UI dependencies)

**Data flow:**
1. `validation.py` — collects all user input (ASNs, neighbor IP, client name, prefixes); offers automatic prefix lookup via `_oferecer_busca_prefixos` before falling back to manual entry
2. `commands.py` — builds Huawei CLI commands (prefix-lists with 10/20/30… index spacing, route-policies, BGP neighbor config); automatically appends `greater-equal`/`less-equal` to each prefix-list entry (IPv4 max /24, IPv6 max /48)
3. `irr.py` — two responsibilities: (a) optional WHOIS validation against whois.radb.net:43; (b) automatic ASN prefix lookup via RIPE Stat API (primary) with IRR/RADB socket fallback; includes subnet deduplication (`_filtrar_subredes`) to keep only aggregate blocks
4. `router_io.py` — parses `routers.txt` (CSV: host,username,password,port) and handles router selection; reports the exact line number on parse errors
5. `connector.py` — SSH lifecycle: TCP pre-check (5 s timeout) → backup current config → apply commands → collect verification output (`display bgp peer`, `display this`); accepts a `confirmar_existente: Callable[[str, str], bool]` callback so it has no UI dependency
6. `report.py` — generates a timestamped PDF with SHA256 hashes of the PDF itself and `routers.txt` for audit compliance

**Supporting modules:**
- `models.py` — three dataclasses: `RouterConfig`, `BgpSessionConfig`, `ExecutionResult`
- `exceptions.py` — `BgpAutomacaoError` hierarchy (5 subclasses); never use bare `sys.exit()` inside library modules
- `config.py` — centralised constants (company name, directory paths, hard limits); all path constants are `Path` objects
- `utils.py` — `sanitize_filename`, `sha256_file`, `filesize_bytes`

### `api/` — FastAPI backend

All routes are under the `/api` prefix.

- `app.py` — FastAPI instance, CORSMiddleware, exception handlers, router inclusion
- `auth.py` — JWT HS256 via `python-jose`; `bcrypt` for password verification; `get_current_user` FastAPI dependency injected in all endpoints
- `schemas.py` — Pydantic v2 request/response models
- `routers/auth.py` — `POST /api/auth/login`
- `routers/sessao.py` — prefix lookup, preview, IRR validation, apply
- `routers/roteadores.py` — inventory list and add
- `routers/relatorios.py` — list and download PDF reports

Blocking sync calls (`executar_bgp`, `buscar_prefixos_por_asn`) are wrapped in `asyncio.to_thread()`.

### `frontend/` — React SPA

- Vite + React 18 + React Router v6 + Axios
- `src/api/client.js` — axios instance; injects `Authorization: Bearer` from localStorage; redirects to `/login` on 401
- `src/context/AuthContext.jsx` — token state, `login()`, `logout()`
- Pages: `Login`, `CriarSessao` (main flow), `Roteadores`, `Relatorios`
- CSS Modules with dark theme (variables in `src/index.css`)

**Output directories** (created at runtime, git-ignored):
- `backups/` — per-router config backups taken before applying changes
- `logs/` — application logs
- `relatorio_huawei_*.pdf` — generated audit reports in project root
- `frontend/dist/` — Vite production build output

## Git & GitHub

Repository: https://github.com/heitortpf/bgp-huawei-automation

**After every change to the project**, commit and push using the full Git path (git is not in Claude Code's PATH):

```powershell
$git = "C:\Program Files\Git\bin\git.exe"
Set-Location "C:\PROJETO BGP"
& $git add .
& $git commit -m "<concise description of what changed>"
& $git push
```

**Never commit:**
- `backend/.env` (JWT secret + admin password hash — already in `.gitignore`)
- `backend/routers.txt` (router credentials in plaintext — already in `.gitignore`)
- `backend/backups/`, `backend/logs/`, `*.pdf`, `log_*.txt` (runtime output — already in `.gitignore`)
- `frontend/node_modules/`, `frontend/dist/` (already in `.gitignore`)

## Key Conventions

- Device type for netmiko is `huawei` (Huawei VRP OS).
- Prefix-list sequence numbers increment by 10 (10, 20, 30…), not 1.
- Prefix-list entries always include `greater-equal`/`less-equal` for blocks smaller than the minimum routable size (IPv4: /24, IPv6: /48). A /24 or /48 exact match gets no suffix.
- When fetching prefixes automatically from RIPE Stat / IRR, always run `_filtrar_subredes` to remove more-specific blocks already covered by an aggregate in the same list.
- `connector.py` is UI-free: all user interaction is injected via the `confirmar_existente` callback. Never add `input()`/`print()` calls directly to `connector.py`.
- `routers.txt` stores credentials in plaintext — known pre-production issue; coordinate with security improvements before exposing to a network.
- All custom exceptions inherit from `BgpAutomacaoError`; raise the most specific subclass available.
- Functions in `connector.py` that touch live routers must perform the TCP pre-check before opening an SSH session.
- All API endpoints require JWT Bearer auth (`Depends(get_current_user)`). The `/api/auth/login` endpoint is the only public route.
- Use `asyncio.to_thread()` for any sync-blocking calls inside async FastAPI endpoints (netmiko, socket I/O).
- Frontend API calls always go through `src/api/client.js` — never use `fetch()` or a raw axios instance elsewhere in the frontend.
