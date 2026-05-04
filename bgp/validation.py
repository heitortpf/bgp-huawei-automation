import ipaddress
import logging
from bgp.irr import buscar_prefixos_por_asn
from bgp.models import BgpSessionConfig
from bgp.exceptions import UserCancelledError

logger = logging.getLogger(__name__)


def _obter_as(mensagem: str) -> int:
    while True:
        try:
            asn = int(input(mensagem).strip())
            if 1 <= asn <= 4_294_967_295:
                return asn
        except ValueError:
            pass
        logger.error("AS inválido. Deve ser um número entre 1 e 4294967295.")


def obter_as_local() -> int:
    return _obter_as("Informe o AS LOCAL: ")


def obter_as_neigh() -> int:
    return _obter_as("Informe o AS DO NEIGHBOR: ")


def obter_ip_neigh() -> str:
    while True:
        try:
            return str(ipaddress.ip_address(input("Informe o IP do NEIGHBOR BGP: ").strip()))
        except ValueError:
            logger.error("IP do neighbor inválido. Tente novamente.")


def obter_nome_cliente() -> str:
    while True:
        nome = input("Informe o nome do cliente (sem espaços, se puder): ").strip()
        if nome:
            return nome
        logger.error("Nome do cliente não pode ser vazio.")


def _obter_prefixo_ipv4() -> str:
    while True:
        try:
            return str(ipaddress.ip_network(
                input("Prefixo IPv4 (ex: 203.0.113.0/24): ").strip(), strict=False
            ))
        except ValueError:
            logger.error("Prefixo IPv4 inválido. Tente novamente.")


def _obter_prefixo_ipv6() -> str:
    while True:
        try:
            return str(ipaddress.ip_network(
                input("Prefixo IPv6 (ex: 2001:db8::/32): ").strip(), strict=False
            ))
        except ValueError:
            logger.error("Prefixo IPv6 inválido. Tente novamente.")


def adicionar_prefixos_ipv4() -> list[str]:
    prefixes: list[str] = []
    print("\n=== PREFIXOS IPv4 ===")
    while True:
        prefixes.append(_obter_prefixo_ipv4())
        if input("Adicionar mais um IPv4? (s/n): ").strip().lower() != "s":
            break
    return prefixes


def adicionar_prefixos_ipv6() -> list[str]:
    prefixes: list[str] = []
    print("\n=== PREFIXOS IPv6 ===")
    while True:
        prefixes.append(_obter_prefixo_ipv6())
        if input("Adicionar mais um IPv6? (s/n): ").strip().lower() != "s":
            break
    return prefixes


def _escolher_tipo_prefixo() -> str:
    print("\n=== TIPO DE PREFIXO ===")
    print("1 - Apenas IPv4")
    print("2 - Apenas IPv6")
    print("3 - IPv4 e IPv6")
    while True:
        opcao = input("Escolha (1/2/3): ").strip()
        if opcao in ("1", "2", "3"):
            return opcao
        logger.error("Opção inválida.")


def perguntar_preview() -> bool:
    return input("\nDeseja ver o preview dos comandos antes de aplicar? (s/n): ").strip().lower() == "s"


def perguntar_validacao_irr() -> bool:
    return input("Deseja validar IRR (RADB) antes de aplicar? (s/n): ").strip().lower() == "s"


def decidir_aplicar_quando_existe(host: str, existente: str) -> bool:
    if not existente:
        return True
    print(f"\n⚠️  Encontrado config relacionada neste roteador: {host}")
    print("----------------------------------------")
    print(existente)
    print("----------------------------------------")
    return input("Quer aplicar mesmo assim neste roteador? (s/n): ").strip().lower() == "s"


def _oferecer_busca_prefixos(asn: int) -> tuple[list[str], list[str]] | None:
    if input(f"\nBuscar prefixos do AS{asn} automaticamente? (s/n): ").strip().lower() != "s":
        return None
    print(f"Consultando prefixos para AS{asn}...", flush=True)
    try:
        v4, v6 = buscar_prefixos_por_asn(asn)
    except Exception as exc:
        logger.error("Busca automática falhou: %s", exc)
        print("Prosseguindo com entrada manual.")
        return None
    if v4:
        print(f"\nIPv4 encontrados ({len(v4)}):")
        for p in v4:
            print(f"  {p}")
    if v6:
        print(f"\nIPv6 encontrados ({len(v6)}):")
        for p in v6:
            print(f"  {p}")
    if input("\nUsar esses prefixos? (s/n): ").strip().lower() != "s":
        return None
    return v4, v6


def confirmar_sessao(session: BgpSessionConfig) -> None:
    print("\n=== CONFIRMAÇÃO ===")
    print(f"AS LOCAL: {session.local_as}")
    print(f"NEIGHBOR: {session.neighbor_ip} AS {session.neighbor_as}")
    print(f"CLIENTE: {session.nome_cliente}")

    if session.prefixes_ipv4:
        print(f"PREFIX-LIST IPv4: {session.nome_prefix_ipv4} -> {', '.join(session.prefixes_ipv4)}")
        print(f"ROUTE-POLICY IPv4: IMPORT {session.rp_imp_v4} | EXPORT {session.rp_exp_v4}")
    else:
        print("IPv4: (não será configurado)")

    if session.prefixes_ipv6:
        print(f"PREFIX-LIST IPv6: {session.nome_prefix_ipv6} -> {', '.join(session.prefixes_ipv6)}")
        print(f"ROUTE-POLICY IPv6: IMPORT {session.rp_imp_v6} | EXPORT {session.rp_exp_v6}")
    else:
        print("IPv6: (não será configurado)")

    if input("\nDeseja aplicar essas configurações? (s/n): ").strip().lower() != "s":
        raise UserCancelledError("Operação cancelada pelo usuário.")


def coletar_sessao() -> BgpSessionConfig:
    local_as = obter_as_local()
    neighbor_ip = obter_ip_neigh()
    neighbor_as = obter_as_neigh()
    nome_cliente = obter_nome_cliente()

    prefixes_ipv4: list[str] = []
    prefixes_ipv6: list[str] = []

    resultado_auto = _oferecer_busca_prefixos(neighbor_as)
    if resultado_auto:
        prefixes_ipv4, prefixes_ipv6 = resultado_auto
    else:
        tipo = _escolher_tipo_prefixo()
        if tipo in ("1", "3"):
            prefixes_ipv4 = adicionar_prefixos_ipv4()
        if tipo in ("2", "3"):
            prefixes_ipv6 = adicionar_prefixos_ipv6()

    return BgpSessionConfig(
        local_as=local_as,
        neighbor_ip=neighbor_ip,
        neighbor_as=neighbor_as,
        nome_cliente=nome_cliente,
        prefixes_ipv4=prefixes_ipv4,
        prefixes_ipv6=prefixes_ipv6,
    )
