# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BGP Huawei Automation Tool — a NOC analyst CLI tool for automating BGP session provisioning on Huawei NE8000 routers (NE8000-F1A/M4). It generates Huawei-specific commands, validates via IRR/RADB, applies configuration over SSH, and generates SHA256-audited PDF reports.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application (interactive CLI)
python main.py
```

No test suite or linter is configured yet (Phase 2 work, per PROGRESSO.md).

## Architecture

The `bgp/` package is the refactored modular core; `script.py` is the original monolithic version kept for reference only. `main.py` is the entry point that wires the modules together.

**Data flow:**
1. `validation.py` — collects all user input (ASNs, neighbor IP, client name, prefixes); offers automatic prefix lookup via `_oferecer_busca_prefixos` before falling back to manual entry
2. `commands.py` — builds Huawei CLI commands (prefix-lists with 10/20/30… index spacing, route-policies, BGP neighbor config); automatically appends `greater-equal`/`less-equal` to each prefix-list entry (IPv4 max /24, IPv6 max /48)
3. `irr.py` — two responsibilities: (a) optional WHOIS validation against whois.radb.net:43; (b) automatic ASN prefix lookup via RIPE Stat API (primary) with IRR/RADB socket fallback; includes subnet deduplication (`_filtrar_subredes`) to keep only aggregate blocks
4. `router_io.py` — parses `routers.txt` (CSV: host,username,password,port) and handles router selection; reports the exact line number on parse errors
5. `connector.py` — SSH lifecycle: TCP pre-check (5 s timeout) → backup current config → apply commands → collect verification output (`display bgp peer`, `display this`); accepts a `confirmar_existente: Callable[[str, str], bool]` callback so it has no UI dependency (ready for FastAPI)
6. `report.py` — generates a timestamped PDF with SHA256 hashes of the PDF itself and `routers.txt` for audit compliance

**Supporting modules:**
- `models.py` — three dataclasses: `RouterConfig`, `BgpSessionConfig`, `ExecutionResult`
- `exceptions.py` — `BgpAutomacaoError` hierarchy (5 subclasses); never use bare `sys.exit()` inside library modules
- `config.py` — centralised constants (company name, directory paths, hard limits); all path constants are `Path` objects
- `utils.py` — `sanitize_filename`, `sha256_file`, `filesize_bytes`

**Output directories** (created at runtime, git-ignored):
- `backups/` — per-router config backups taken before applying changes
- `logs/` — application logs
- `relatorio_huawei_*.pdf` — generated audit reports in project root

## Key Conventions

- Device type for netmiko is `huawei` (Huawei VRP OS).
- Prefix-list sequence numbers increment by 10 (10, 20, 30…), not 1.
- Prefix-list entries always include `greater-equal`/`less-equal` for blocks smaller than the minimum routable size (IPv4: /24, IPv6: /48). A /24 or /48 exact match gets no suffix.
- When fetching prefixes automatically from RIPE Stat / IRR, always run `_filtrar_subredes` to remove more-specific blocks already covered by an aggregate in the same list.
- `connector.py` is UI-free: all user interaction is injected via the `confirmar_existente` callback. Never add `input()`/`print()` calls directly to `connector.py`.
- `routers.txt` stores credentials in plaintext — this is a known pre-production issue; do not add encryption without coordinating with the planned FastAPI backend (Phase 2).
- All custom exceptions inherit from `BgpAutomacaoError`; raise the most specific subclass available.
- Functions in `connector.py` that touch live routers must perform the TCP pre-check before opening an SSH session.
