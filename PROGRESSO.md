# Projeto BGP Huawei — Progresso

## Contexto
Ferramenta de automação para criação de sessões BGP em roteadores Huawei NE8000 (F1A/M4), desenvolvida por analista de NOC. Automatiza geração de comandos, validação IRR/RADB, backup pré-change, aplicação via SSH e geração de relatório PDF com hash SHA256 para auditoria.

---

## O que foi feito

### Fase 1 — Refatoração (CONCLUÍDA)

O `script.py` original (759 linhas, monolítico) foi refatorado em pacote modular:

```
PROJETO BGP\
├── backend\
│   ├── main.py              ← ponto de entrada CLI
│   ├── requirements.txt
│   ├── script.py            ← original intacto (não apagar)
│   └── bgp\
    ├── __init__.py
    ├── config.py        ← constantes (ARQUIVO_ROUTERS, EMPRESA, BACKUP_DIR...) — todos Path
    ├── exceptions.py    ← BgpAutomacaoError, IrrValidationError, RouterConnectionError,
    │                       RouterInventoryError, UserCancelledError
    ├── models.py        ← dataclasses: RouterConfig, BgpSessionConfig, ExecutionResult
    ├── utils.py         ← sha256_file, filesize_bytes, sanitize_filename
    ├── irr.py           ← buscar_prefixos_por_asn (RIPE Stat + IRR fallback),
    │                       _filtrar_subredes, validar_asn_prefixo
    ├── validation.py    ← todos os inputs + _oferecer_busca_prefixos + coletar_sessao
    ├── commands.py      ← build_huawei_commands (com ge/le automático), preview_commands
    ├── router_io.py     ← ler_routers_txt (com nº de linha no erro), escolher_roteadores
    ├── connector.py     ← TCP pre-check, SSH, backup, coletas, executar_bgp (callback)
    └── report.py        ← _build_pdf, gerar_relatorio
```

#### Bugs corrigidos
| Bug | Antes | Depois |
|---|---|---|
| Índice prefix-list | `10, 11, 12...` | `10, 20, 30...` (convenção Huawei) |
| `obter_nome_cliente` | recursão (risco stack overflow) | `while True` loop |
| Funções de biblioteca | chamavam `sys.exit()` | lançam exceções nomeadas |
| `gerar_policies_e_prefixos` | retornava tupla de 6 valores | properties no `BgpSessionConfig` |

#### Melhorias e features adicionadas
| Feature | Descrição |
|---|---|
| TCP pre-check | Antes de cada SSH: falha rápida em 5s se host inacessível |
| Dataclasses com type hints | Em todos os módulos (Python 3.9+) |
| Exceções por categoria | Tratadas individualmente no `main.py` |
| `coletar_sessao()` | Orquestra toda coleta de inputs, retorna `BgpSessionConfig` |
| `sys.exit()` apenas no `main.py` | Módulos internos não encerram o processo |
| **ge/le automático** | Prefix-lists IPv4 recebem `greater-equal X less-equal 24`; IPv6 recebem `greater-equal X less-equal 48`; blocos /24 e /48 ficam sem sufixo |
| **Busca automática de prefixos** | Ao digitar o ASN do cliente, oferece busca via RIPE Stat API (primário) e IRR/RADB socket (fallback); sem novas dependências (stdlib `urllib.request` + `json`) |
| **Deduplicação de subredes** | `_filtrar_subredes` remove prefixos cobertos por agregados na mesma lista, evitando entradas redundantes no prefix-list |
| **Callback `confirmar_existente`** | `connector.py` não depende mais de `validation.py`; a decisão de aplicar sobre config existente é injetada via `Callable[[str, str], bool]` |
| **Número de linha no erro de parse** | `router_io.py` reporta a linha exata do `routers.txt` quando o formato está inválido |

---

### Fase 2 — Backend FastAPI (CONCLUÍDA)

Toda a lógica do `bgp/` exposta como API REST via FastAPI + uvicorn. Todos os endpoints sob o prefixo `/api`.

```
api\
├── __init__.py
├── app.py          ← instância FastAPI, CORSMiddleware, exception handlers, routers
├── auth.py         ← JWT HS256 (python-jose), verificação bcrypt, dependency get_current_user
├── schemas.py      ← modelos Pydantic v2 (request + response + HistoricoItemResponse)
└── routers\
    ├── auth.py       ← POST /api/auth/login
    ├── sessao.py     ← GET  /api/sessao/asn/{asn}/prefixos
    │                    POST /api/sessao/preview
    │                    POST /api/sessao/validar-irr
    │                    POST /api/sessao/aplicar
    │                    POST /api/sessao/aplicar-stream  ← SSE (Fase 5)
    ├── roteadores.py ← GET    /api/roteadores
    │                    POST   /api/roteadores
    │                    DELETE /api/roteadores/{host}
    ├── relatorios.py ← GET /api/relatorios (lista PDFs)
    │                    GET /api/relatorios/{nome} (download)
    └── historico.py  ← GET /api/historico          ← Fase 5
                         GET /api/historico/{id}
api_main.py         ← python api_main.py → sobe em 0.0.0.0:8000; chama init_db()
```

#### Detalhes de implementação
| Item | Detalhe |
|---|---|
| Autenticação | JWT HS256, expiração configurável (padrão 8h), senha com bcrypt |
| Proteção | Todos os endpoints exigem `Authorization: Bearer <token>` |
| Operações síncronas | `executar_bgp()`, `buscar_prefixos_por_asn()`, `salvar_sessao()` chamados via `asyncio.to_thread()` |
| CORS | Origens liberadas: `localhost:5173` (Vite dev) e `localhost:4173` (Vite preview) |
| Exception mapping | `IrrValidationError`→422, `RouterConnectionError`→503, `RouterInventoryError`→500 |
| Credenciais | `.env` com `JWT_SECRET`, `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH`, `JWT_EXPIRE_HOURS` |

---

### Fase 3 — Interface Web React (CONCLUÍDA)

SPA React 18 + Vite servida em `localhost:5173` (dev) com proxy para a API FastAPI em `:8000`.

```
frontend\
├── package.json          ← react, react-dom, react-router-dom, axios
├── vite.config.js        ← proxy /api → http://localhost:8000
├── index.html
└── src\
    ├── main.jsx
    ├── App.jsx             ← React Router v6: rotas públicas + privadas
    ├── index.css           ← variáveis CSS globais (tema escuro)
    ├── api\
    │   └── client.js       ← axios + interceptor Bearer + redirect 401
    ├── context\
    │   └── AuthContext.jsx ← token em localStorage, login/logout
    ├── utils\
    │   └── download.js     ← downloadBlob(blob, filename) compartilhado
    ├── components\
    │   ├── Layout.jsx          ← navbar + links (Nova Sessão, Roteadores, Histórico, Relatórios) + logout
    │   ├── Layout.module.css
    │   └── PrivateRoute.jsx    ← redirect /login se sem token
    └── pages\
        ├── Login.jsx           ← POST /api/auth/login
        ├── Login.module.css
        ├── CriarSessao.jsx     ← fluxo principal com painel de log SSE
        ├── Roteadores.jsx      ← GET/POST/DELETE /api/roteadores
        ├── Relatorios.jsx      ← lista + download de PDFs
        ├── Historico.jsx       ← tabela expansível de sessões + download PDF  ← Fase 5
        └── Page.module.css     ← CSS compartilhado entre páginas
```

#### Fluxo da página Criar Sessão (com SSE)
1. Preencher Local AS, Neighbor IP, Neighbor AS, Nome Cliente
2. Botão **"Buscar pelo AS"** → `GET /api/sessao/asn/{neighbor_as}/prefixos` → auto-preenche listas IPv4/IPv6
3. Botão **"Gerar Preview"** → `POST /api/sessao/preview` → exibe comandos Huawei gerados
4. Selecionar roteadores (checkboxes) + toggles "Aplicar se já existir" / "Gerar relatório PDF"
5. Botão **"Aplicar nos Roteadores"** → `POST /api/sessao/aplicar-stream` → painel de log ao vivo por etapa (TCP, SSH, backup, comandos, BGP peer) → tabela de resultados ao final
6. Botão **"Baixar PDF"** aparece se relatório foi gerado

---

### Fase 4 — Refatoração e limpeza técnica (CONCLUÍDA)

| Arquivo | Mudança |
|---|---|
| `router_io.py` | I/O via módulo `csv` — sem CSV injection; `acrescentar_router()` e `remover_router()` |
| `roteadores.py` | Delega todo I/O ao `router_io`; erros viram HTTP exceptions adequadas; endpoint DELETE |
| `sessao.py` | `roteadores: None` = todos, `[]` = HTTP 400; retorna `relatorio_nome` (só o filename) |
| `schemas.py` | `roteadores: list[str] | None = None`; `relatorio_nome` no lugar de `relatorio_path` |
| `relatorios.py` | Validação por regex `^relatorio_huawei_\d{8}_\d{6}\.pdf$` |
| `Layout.module.css` | Bloco `:root`/`*`/`body` duplicado removido (fonte única: `index.css`) |
| `Page.module.css` | Classes `.cardHeader` e `.btnDelete` adicionadas |
| `utils/download.js` | Helper `downloadBlob` extraído e compartilhado |
| `CriarSessao.jsx`, `Relatorios.jsx`, `Roteadores.jsx` | Sem estilos inline, sem lógica de blob duplicada |

---

### Fase 5 — SSE + Histórico SQLite + Testes Automatizados (CONCLUÍDA)

#### A — Testes automatizados (`backend/tests/`)
- `requirements-dev.txt`: pytest + pytest-cov + httpx
- `conftest.py`: fixture `client` (TestClient + override de auth JWT), fixture `tmp_routers_file`
- `test_commands.py`: 9 testes de funções puras (`_ge_le_suffix`, `build_huawei_commands`)
- `test_irr.py`: 8 testes — `_filtrar_subredes` + mocks de rede RIPE/IRR socket
- `test_api.py`: 13 testes de integração — login, preview, CRUD roteadores, edge cases do aplicar
- **30 testes passando** — rodar com `python -m pytest tests/ -q` dentro de `backend/`

#### B — SSE: feedback em tempo real
- `connector.py`: parâmetro `on_progress: Callable[[dict], None] | None` + helper `_emit()`; emite 5 eventos por roteador (tcp_check, ssh_connected, backup_done, commands_sent, verification_done) + evento `result` ao final de cada roteador
- `sessao.py`: novo endpoint `POST /api/sessao/aplicar-stream` — bridge `asyncio.Queue` entre callback síncrono do threadpool e gerador assíncrono do `StreamingResponse`; usa `asyncio.get_running_loop()` (não `get_event_loop()`)
- `CriarSessao.jsx`: `handleAplicar` usa `fetch()` + `ReadableStream` (POST com headers — `EventSource` é GET-only); painel de log `.logPanel` aparece durante a execução; `AbortController` cancela o stream no unmount

#### C — Histórico de sessões (SQLite)
- `bgp/db.py`: SQLite stdlib — `_DB_PATH = backend/historico.db`; `init_db()`, `salvar_sessao()`, `listar_sessoes(limit=100)`, `buscar_sessao(id)`, `_row_to_dict()` (deserializa JSON)
- `api_main.py`: chama `init_db()` antes de subir o uvicorn
- `sessao.py`: `salvar_sessao()` chamado em `asyncio.to_thread()` ao final de `/aplicar` e `/aplicar-stream`; falha no DB não derruba o endpoint (swallow com log)
- `schemas.py`: `HistoricoItemResponse` adicionado
- `routers/historico.py`: `GET /api/historico` e `GET /api/historico/{id}` com autenticação JWT
- `Historico.jsx`: tabela com linhas expansíveis (estado `Set`); mostra status resumido (X/N OK), detalhes por roteador, link de download do PDF se houver
- `Layout.jsx` + `App.jsx`: link "Histórico" na navbar e rota `/historico`

---

### Otimização pós-Fase 5 (CONCLUÍDA — commit afc24b7 / aa8094c)

| Arquivo | Correção |
|---|---|
| `connector.py` | Fix vazamento de conexão SSH: `conn = None` antes do try; `conn.disconnect()` no except |
| `sessao.py` | `asyncio.get_event_loop()` → `asyncio.get_running_loop()`; remoção de try/except morto em `validar_irr` |
| `db.py` | Adicionado logging; `salvar_sessao` envolto em try/except — falha no DB não derruba `/aplicar` |
| `Historico.jsx` | `<>` → `<React.Fragment key={s.id}>` no `.map()` (fix React reconciliation warning) |
| `CriarSessao.jsx` | `.catch` no `useEffect` de roteadores; try/catch no `handleDownloadPdf`; `r.duracao_s?.toFixed(1) ?? "-"` (optional chain); `AbortController` para cancelar stream no unmount |

---

## Status atual

- [x] Fase 1 — Refatoração do script.py para pacote `bgp/`
- [x] ge/le automático nos prefix-lists
- [x] Busca automática de prefixos por ASN (RIPE Stat + IRR fallback)
- [x] Deduplicação de subredes
- [x] Fase 2 — Backend FastAPI com todos os endpoints
- [x] Autenticação JWT (python-jose + bcrypt)
- [x] Fase 3 — Interface Web React (Vite, React Router, Axios)
- [x] Fase 4 — Refatoração técnica (csv, regex, download helper, CSS)
- [x] Fase 5A — Testes automatizados (30 testes passando)
- [x] Fase 5B — SSE: painel de log ao vivo durante aplicação
- [x] Fase 5C — Histórico de sessões SQLite com página na UI
- [x] Otimização: connection leak, AbortController, React.Fragment key, error handling
- [ ] Segurança de produção (HTTPS, credenciais de roteadores fora de texto plano)
- [ ] Paginação no histórico (hoje: limit=100 fixo)
