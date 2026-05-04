import ipaddress
import json
import socket
import logging
import urllib.request
from bgp.exceptions import IrrValidationError

logger = logging.getLogger(__name__)

_WHOIS_SERVER = "whois.radb.net"
_WHOIS_PORT = 43


def _filtrar_subredes(prefixes: list[str]) -> list[str]:
    """Remove prefixes cobertos por um agregado já presente na lista, mantendo só os maiores blocos."""
    nets = sorted(
        [ipaddress.ip_network(p, strict=False) for p in prefixes],
        key=lambda n: n.prefixlen,
    )
    keepers: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for net in nets:
        if not any(net.subnet_of(k) for k in keepers):
            keepers.append(net)
    return [str(n) for n in keepers]


def buscar_prefixos_por_asn(asn: int) -> tuple[list[str], list[str]]:
    """Retorna (prefixes_ipv4, prefixes_ipv6) para o ASN. Tenta RIPE Stat, fallback IRR."""
    try:
        v4, v6 = _buscar_ripe_stat(asn)
    except Exception as exc:
        logger.warning("RIPE Stat falhou (%s), tentando IRR/RADB...", exc)
        v4, v6 = _buscar_irr_socket(asn)
    return _filtrar_subredes(v4), _filtrar_subredes(v6)


def _buscar_ripe_stat(asn: int) -> tuple[list[str], list[str]]:
    url = f"https://stat.ripe.net/data/announced-prefixes/data.json?resource=AS{asn}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        data = json.loads(resp.read())
    prefixes = [p["prefix"] for p in data["data"]["prefixes"]]
    v4 = sorted(p for p in prefixes if ":" not in p)
    v6 = sorted(p for p in prefixes if ":" in p)
    if not v4 and not v6:
        raise IrrValidationError(f"Nenhum prefixo encontrado para AS{asn} no RIPE Stat")
    return v4, v6


def _buscar_irr_socket(asn: int) -> tuple[list[str], list[str]]:
    with socket.create_connection((_WHOIS_SERVER, _WHOIS_PORT), timeout=10) as s:
        s.sendall(f"!gAS{asn}\n".encode())
        resp = b""
        while chunk := s.recv(4096):
            resp += chunk
    prefixes = []
    for line in resp.decode(errors="ignore").splitlines():
        line = line.strip()
        if line and not line.startswith(("%", "A ", "C", "D", "F")):
            prefixes.extend(line.split())
    v4 = sorted(p for p in prefixes if "/" in p and ":" not in p)
    v6 = sorted(p for p in prefixes if ":" in p)
    if not v4 and not v6:
        raise IrrValidationError(f"Nenhum prefixo encontrado para AS{asn} no IRR/RADB")
    return v4, v6


def validar_asn_prefixo(prefixos: list[str], asn_peer: int) -> None:
    logger.info("Validando prefixos contra ASN via IRR (RADB)...")
    origins_encontrados: set[str] = set()

    for prefixo in prefixos:
        try:
            with socket.create_connection((_WHOIS_SERVER, _WHOIS_PORT), timeout=10) as s:
                s.sendall(f"{prefixo}\n".encode())
                resposta = b""
                while True:
                    data = s.recv(4096)
                    if not data:
                        break
                    resposta += data
        except Exception as e:
            raise IrrValidationError(f"Erro ao consultar IRR/RADB para '{prefixo}': {e}") from e

        rota_atual = None
        for linha in resposta.decode(errors="ignore").lower().splitlines():
            linha = linha.strip()
            if linha.startswith(("route:", "route6:")):
                rota_atual = linha.split(":", 1)[1].strip()
            if linha.startswith("origin:") and rota_atual:
                asn = linha.split(":", 1)[1].strip().replace("as", "")
                origins_encontrados.add(asn)

    if str(asn_peer) not in origins_encontrados:
        found = ", ".join(origins_encontrados) or "nenhum"
        raise IrrValidationError(
            f"ASN do peer informado: AS{asn_peer} | ASN(s) encontrados no IRR: {found}"
        )

    logger.info("Validação IRR OK: origin ASN confere com ASN do peer.")
