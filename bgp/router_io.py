import logging
from pathlib import Path
from bgp.config import ARQUIVO_ROUTERS
from bgp.models import RouterConfig
from bgp.exceptions import RouterInventoryError

logger = logging.getLogger(__name__)


def ler_routers_txt(path: Path | str = ARQUIVO_ROUTERS) -> list[RouterConfig]:
    routers: list[RouterConfig] = []
    try:
        with open(path, encoding="utf-8") as f:
            for num, linha in enumerate(f, start=1):
                linha = linha.strip()
                if not linha or linha.startswith("#"):
                    continue
                try:
                    host, user, pwd, port = linha.split(",")
                except ValueError as e:
                    raise RouterInventoryError(
                        f"Erro ao ler '{path}', linha {num}: formato inválido ({e!r})"
                    ) from e
                routers.append(RouterConfig(
                    host=host.strip(),
                    username=user.strip(),
                    password=pwd.strip(),
                    port=int(port.strip()),
                ))
    except RouterInventoryError:
        raise
    except Exception as e:
        raise RouterInventoryError(f"Erro ao ler o arquivo de roteadores '{path}': {e}") from e

    if not routers:
        raise RouterInventoryError(f"Nenhum roteador encontrado em '{path}'.")

    return routers


def escolher_roteadores(routers: list[RouterConfig]) -> list[RouterConfig]:
    print("\n=== SELEÇÃO DE ROTEADORES ===")
    print("1 - Aplicar em TODOS os roteadores")
    print("2 - Aplicar em APENAS UM roteador")

    while True:
        opcao = input("Escolha (1/2): ").strip()
        if opcao == "1":
            return routers
        if opcao == "2":
            for i, r in enumerate(routers, 1):
                print(f"  {i} - {r.host}:{r.port}")
            while True:
                try:
                    idx = int(input("Escolha o número: ").strip())
                    if 1 <= idx <= len(routers):
                        return [routers[idx - 1]]
                except ValueError:
                    pass
                logger.error("Seleção inválida. Tente novamente.")
        logger.error("Opção inválida.")
