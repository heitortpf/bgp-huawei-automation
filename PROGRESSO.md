# Projeto BGP Huawei — Progresso

## Contexto
Ferramenta de automação para criação de sessões BGP em roteadores Huawei NE8000 (F1A/M4), desenvolvida por analista de NOC. Automatiza geração de comandos, validação IRR/RADB, backup pré-change, aplicação via SSH e geração de relatório PDF com hash SHA256 para auditoria.

---

## O que foi feito

### Fase 1 — Refatoração (CONCLUÍDA)

O `script.py` original (759 linhas, monolítico) foi refatorado em pacote modular:

```
PROJETO BGP\
├── main.py              ← ponto de entrada
├── requirements.txt     ← netmiko>=4.0.0, reportlab>=4.0.0
├── script.py            ← original intacto (não apagar)
└── bgp\
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
| **Callback `confirmar_existente`** | `connector.py` não depende mais de `validation.py`; a decisão de aplicar sobre config existente é injetada via `Callable[[str, str], bool]` — pronto para FastAPI |
| **Número de linha no erro de parse** | `router_io.py` reporta a linha exata do `routers.txt` quando o formato está inválido |
| **`ARQUIVO_ROUTERS` como `Path`** | Consistência com `BACKUP_DIR` e `LOG_DIR` em `config.py` |

#### Como rodar
```bash
cd "C:\PROJETO BGP"
python main.py
```

---

## Próximas fases (planejadas)

### Fase 2 — Backend FastAPI
- Expor toda a lógica do pacote `bgp/` como API REST
- `connector.py` já está preparado (sem dependência de UI, callback injetável)
- Endpoints planejados:
  - `POST /sessao/preview` — retorna os comandos gerados sem aplicar
  - `POST /sessao/aplicar` — executa nos roteadores e retorna resultados
  - `GET /roteadores` — lista inventário
  - `POST /roteadores` — adiciona roteador
  - `GET /relatorios/{nome}` — download do PDF gerado
- Resolver segurança das credenciais (hoje em texto plano no `routers.txt`)

### Fase 3 — Interface Web
- Formulário de criação de sessão BGP (substitui o input interativo no terminal)
- Gerenciamento de inventário de roteadores (substitui `routers.txt` manual)
- Preview visual dos comandos antes de aplicar
- Status em tempo real da execução SSH (WebSocket ou SSE)
- Histórico de sessões configuradas
- Download do PDF de relatório
- Stack sugerida: FastAPI + HTML/HTMX (simples) ou React (mais dinâmico)

### Itens de segurança pendentes
- Credenciais dos roteadores ainda em texto plano no `routers.txt` — avaliar uso de variáveis de ambiente ou cofre de senhas antes de produção
- Adicionar autenticação na interface web antes de expor em rede

---

## Status atual
- [x] Fase 1 — Refatoração
- [x] ge/le automático nos prefix-lists
- [x] Busca automática de prefixos por ASN (RIPE Stat + IRR fallback)
- [x] Deduplicação de subredes na busca automática
- [x] Limpeza arquitetural pré-Fase 2 (connector desacoplado, imports consistentes)
- [ ] Fase 2 — Backend FastAPI
- [ ] Fase 3 — Interface Web
