import ipaddress
import logging
from bgp.models import BgpSessionConfig

logger = logging.getLogger(__name__)

_MAX_IPV4 = 24
_MAX_IPV6 = 48


def _ge_le_suffix(prefix: str) -> str:
    net = ipaddress.ip_network(prefix, strict=False)
    plen = net.prefixlen
    max_len = _MAX_IPV4 if isinstance(net, ipaddress.IPv4Network) else _MAX_IPV6
    if plen >= max_len:
        return ""
    return f" greater-equal {plen} less-equal {max_len}"


def build_huawei_commands(session: BgpSessionConfig) -> list[str]:
    cmds: list[str] = ["system-view"]

    if session.prefixes_ipv4:
        for i, pfx in enumerate(session.prefixes_ipv4):
            cmds.append(f"ip ip-prefix {session.nome_prefix_ipv4} index {(i + 1) * 10} permit {pfx}{_ge_le_suffix(pfx)}")
        cmds += [
            f"route-policy {session.rp_imp_v4} permit node 10",
            f" if-match ip-prefix {session.nome_prefix_ipv4}",
            " quit",
            f"route-policy {session.rp_imp_v4} deny node 500",
            " quit",
            f"route-policy {session.rp_exp_v4} permit node 10",
            " quit",
            f"route-policy {session.rp_exp_v4} deny node 500",
            " quit",
        ]

    if session.prefixes_ipv6:
        for i, pfx in enumerate(session.prefixes_ipv6):
            cmds.append(f"ip ipv6-prefix {session.nome_prefix_ipv6} index {(i + 1) * 10} permit {pfx}{_ge_le_suffix(pfx)}")
        cmds += [
            f"route-policy {session.rp_imp_v6} permit node 10",
            f" if-match ipv6 address prefix-list {session.nome_prefix_ipv6}",
            " quit",
            f"route-policy {session.rp_imp_v6} deny node 500",
            " quit",
            f"route-policy {session.rp_exp_v6} permit node 10",
            " quit",
            f"route-policy {session.rp_exp_v6} deny node 500",
            " quit",
        ]

    cmds += [
        f"bgp {session.local_as}",
        f" peer {session.neighbor_ip} as-number {session.neighbor_as}",
    ]

    if session.prefixes_ipv4:
        cmds += [
            " ipv4-family unicast",
            f"  peer {session.neighbor_ip} enable",
            f"  peer {session.neighbor_ip} route-policy {session.rp_imp_v4} import",
            f"  peer {session.neighbor_ip} route-policy {session.rp_exp_v4} export",
        ]

    if session.prefixes_ipv6:
        cmds += [
            " ipv6-family unicast",
            f"  peer {session.neighbor_ip} enable",
            f"  peer {session.neighbor_ip} route-policy {session.rp_imp_v6} import",
            f"  peer {session.neighbor_ip} route-policy {session.rp_exp_v6} export",
        ]

    cmds.append("return")
    return cmds


def preview_commands(cmds: list[str]) -> None:
    print("\n=== PREVIEW DOS COMANDOS (Huawei NE8000) ===")
    for c in cmds:
        print(c)
    print("=== FIM DO PREVIEW ===\n")
