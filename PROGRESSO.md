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
├── schemas.py      ← modelos Pydantic v2 (request + response)
└── routers\
    ├── auth.py       ← POST /api/auth/login
    ├── sessao.py     ← GET /api/sessao/asn/{asn}/prefixos
    │                    POST /api/sessao/preview
    │                    POST /api/sessao/validar-irr
    │                    POST /api/sessao/aplicar
    ├── roteadores.py ← GET /api/roteadores
    │                    POST /api/roteadores
    └── relatorios.py ← GET /api/relatorios (lista PDFs)
                         GET /api/relatorios/{nome} (download)
api_main.py         ← python api_main.py → sobe em 0.0.0.0:8000
```

#### Detalhes de implementação
| Item | Detalhe |
|---|---|
| Autenticação | JWT HS256, expiração configurável (padrão 8h), senha com bcrypt |
| Proteção | Todos os endpoints exigem `Authorization: Bearer <token>` |
| Operações síncronas | `executar_bgp()` e `buscar_prefixos_por_asn()` chamados via `asyncio.to_thread()` |
| CORS | Origens liberadas: `localhost:5173` (Vite dev) e `localhost:4173` (Vite preview) |
| Exception mapping | `IrrValidationError`→422, `RouterConnectionError`→503, `RouterInventoryError`→500 |
| Credenciais | `.env` com `JWT_SECRET`, `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH`, `JWT_EXPIRE_HOURS` |

#### Como rodar
```powershell
cd backend
python api_main.py   # → http://localhost:8000/docs (Swagger UI)
```

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
    ├── components\
    │   ├── Layout.jsx          ← navbar + links + botão logout
    │   ├── Layout.module.css
    │   └── PrivateRoute.jsx    ← redirect /login se sem token
    └── pages\
        ├── Login.jsx           ← POST /api/auth/login
        ├── Login.module.css
        ├── CriarSessao.jsx     ← fluxo principal (ver abaixo)
        ├── Roteadores.jsx      ← GET/POST /api/roteadores
        ├── Relatorios.jsx      ← lista + download de PDFs
        └── Page.module.css     ← CSS compartilhado entre páginas
```

#### Fluxo da página Criar Sessão
1. Preencher Local AS, Neighbor IP, Neighbor AS, Nome Cliente
2. Botão **"Buscar pelo AS"** → `GET /api/sessao/asn/{neighbor_as}/prefixos` → auto-preenche listas IPv4/IPv6
3. Botão **"Gerar Preview"** → `POST /api/sessao/preview` → exibe comandos Huawei gerados
4. Selecionar roteadores (checkboxes) + toggles "Aplicar se já existir" / "Gerar relatório PDF"
5. Botão **"Aplicar nos Roteadores"** → `POST /api/sessao/aplicar` → tabela de resultados por roteador
6. Botão **"Baixar PDF"** aparece se relatório foi gerado

#### Como rodar (desenvolvimento)
```powershell
# Terminal 1 — Backend
cd backend
python api_main.py

# Terminal 2 — Frontend
cd frontend
npm run dev      # → http://localhost:5173
```

Login padrão configurado em `backend/.env`: `admin` / `admin123` (altere antes de expor em rede).

---

## Status atual

- [x] Fase 1 — Refatoração do script.py para pacote `bgp/`
- [x] ge/le automático nos prefix-lists
- [x] Busca automática de prefixos por ASN (RIPE Stat + IRR fallback)
- [x] Deduplicação de subredes
- [x] Fase 2 — Backend FastAPI com todos os endpoints
- [x] Autenticação JWT (python-jose + bcrypt)
- [x] Fase 3 — Interface Web React (Vite, React Router, Axios)
- [ ] Testes automatizados (pytest para `bgp/` + testes de integração da API)
- [ ] Segurança de produção (HTTPS, credenciais de roteadores fora de texto plano)
