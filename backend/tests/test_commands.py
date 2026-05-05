import pytest
from bgp.models import BgpSessionConfig
from bgp.commands import _ge_le_suffix, build_huawei_commands


def _session(**kwargs) -> BgpSessionConfig:
    defaults = dict(
        local_as=65001,
        neighbor_ip="10.0.0.1",
        neighbor_as=28571,
        nome_cliente="CLIENTE_X",
        prefixes_ipv4=[],
        prefixes_ipv6=[],
    )
    return BgpSessionConfig(**{**defaults, **kwargs})


# --- _ge_le_suffix ---

def test_ge_le_suffix_exact_ipv4():
    assert _ge_le_suffix("200.0.0.0/24") == ""


def test_ge_le_suffix_smaller_ipv4():
    assert _ge_le_suffix("200.0.0.0/20") == " greater-equal 20 less-equal 24"


def test_ge_le_suffix_host_ipv4():
    assert _ge_le_suffix("200.0.0.1/32") == ""


def test_ge_le_suffix_exact_ipv6():
    assert _ge_le_suffix("2001:db8::/48") == ""


def test_ge_le_suffix_smaller_ipv6():
    assert _ge_le_suffix("2001:db8::/40") == " greater-equal 40 less-equal 48"


# --- build_huawei_commands ---

def test_build_commands_starts_and_ends():
    cmds = build_huawei_commands(_session(prefixes_ipv4=["10.0.0.0/24"]))
    assert cmds[0] == "system-view"
    assert cmds[-1] == "return"


def test_build_commands_prefix_list_numbering():
    session = _session(prefixes_ipv4=["10.0.0.0/20", "10.1.0.0/20", "10.2.0.0/20"])
    cmds = build_huawei_commands(session)
    pl = [c for c in cmds if "ip ip-prefix" in c]
    assert "index 10" in pl[0]
    assert "index 20" in pl[1]
    assert "index 30" in pl[2]


def test_build_commands_has_bgp_neighbor():
    cmds = build_huawei_commands(_session(prefixes_ipv4=["10.0.0.0/24"]))
    assert any("peer 10.0.0.1 as-number 28571" in c for c in cmds)


def test_build_commands_no_ipv4_prefixes():
    cmds = build_huawei_commands(_session(prefixes_ipv6=["2001:db8::/32"]))
    assert not any("ip ip-prefix" in c for c in cmds)
    assert any("ip ipv6-prefix" in c for c in cmds)


def test_build_commands_no_ipv6_prefixes():
    cmds = build_huawei_commands(_session(prefixes_ipv4=["10.0.0.0/24"]))
    assert not any("ipv6-prefix" in c for c in cmds)
    assert any("ip ip-prefix" in c for c in cmds)


def test_build_commands_ge_le_applied():
    cmds = build_huawei_commands(_session(prefixes_ipv4=["10.0.0.0/20"]))
    pl = [c for c in cmds if "ip ip-prefix" in c]
    assert "greater-equal 20 less-equal 24" in pl[0]


def test_build_commands_route_policy_names():
    session = _session(prefixes_ipv4=["10.0.0.0/24"])
    cmds = build_huawei_commands(session)
    joined = "\n".join(cmds)
    assert "CLI-BGP-CLIENTE_X-IPv4-IMPORT" in joined
    assert "CLI-BGP-CLIENTE_X-IPv4-EXPORT" in joined
