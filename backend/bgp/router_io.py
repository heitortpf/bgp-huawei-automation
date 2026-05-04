import csv
import logging
from pathlib import Path
from bgp.config import ARQUIVO_ROUTERS
from bgp.models import RouterConfig
from bgp.exceptions import RouterInventoryError

logger = logging.getLogger(__name__)


def ler_routers_txt(path: Path | str = ARQUIVO_ROUTERS) -> list[RouterConfig]:
    routers: list[RouterConfig] = []
    try:
        with open(path, newline="", encoding="utf-8") as f:
            for num, row in enumerate(csv.reader(f), start=1):
                if not row or row[0].startswith("#"):
                    continue
                if len(row) != 4:
                    raise RouterInventoryError(
                        f"Erro ao ler '{path}', linha {num}: esperado 4 campos, encontrado {len(row)}"
                    )
                host, user, pwd, port = (c.strip() for c in row)
                routers.append(RouterConfig(host=host, username=user, password=pwd, port=int(port)))
    except RouterInventoryError:
        raise
    except Exception as e:
        raise RouterInventoryError(f"Erro ao ler o arquivo de roteadores '{path}': {e}") from e

    if not routers:
        raise RouterInventoryError(f"Nenhum roteador encontrado em '{path}'.")

    return routers


def acrescentar_router(router: RouterConfig, path: Path | str = ARQUIVO_ROUTERS) -> None:
    with open(path, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([router.host, router.username, router.password, router.port])


def remover_router(host: str, path: Path | str = ARQUIVO_ROUTERS) -> bool:
    try:
        routers = ler_routers_txt(path)
    except RouterInventoryError:
        return False
    restantes = [r for r in routers if r.host != host]
    if len(restantes) == len(routers):
        return False
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for r in restantes:
            w.writerow([r.host, r.username, r.password, r.port])
    return True


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
