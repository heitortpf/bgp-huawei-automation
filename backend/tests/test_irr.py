import json
import pytest
from unittest.mock import patch, MagicMock
from bgp.irr import _filtrar_subredes, buscar_prefixos_por_asn


# --- _filtrar_subredes (pure function) ---

def test_filtrar_subredes_removes_specific_covered_by_aggregate():
    result = _filtrar_subredes(["10.0.0.0/20", "10.0.0.0/24"])
    assert "10.0.0.0/20" in result
    assert "10.0.0.0/24" not in result


def test_filtrar_subredes_keeps_disjoint_blocks():
    result = _filtrar_subredes(["10.0.0.0/20", "192.168.0.0/24"])
    assert "10.0.0.0/20" in result
    assert "192.168.0.0/24" in result


def test_filtrar_subredes_empty_list():
    assert _filtrar_subredes([]) == []


def test_filtrar_subredes_single_prefix():
    result = _filtrar_subredes(["200.0.0.0/20"])
    assert result == ["200.0.0.0/20"]


def test_filtrar_subredes_ipv6_removes_specific():
    result = _filtrar_subredes(["2001:db8::/32", "2001:db8::/48"])
    assert "2001:db8::/32" in result
    assert "2001:db8::/48" not in result


# --- buscar_prefixos_por_asn (mocked network) ---

def _make_ripe_mock(prefixes: list[str]) -> MagicMock:
    data = {"data": {"prefixes": [{"prefix": p} for p in prefixes]}}
    m = MagicMock()
    m.read.return_value = json.dumps(data).encode()
    m.__enter__ = MagicMock(return_value=m)
    m.__exit__ = MagicMock(return_value=False)
    return m


def test_buscar_prefixos_ripe_ok():
    mock_resp = _make_ripe_mock(["200.0.0.0/20", "2001:db8::/32"])
    with patch("urllib.request.urlopen", return_value=mock_resp):
        v4, v6 = buscar_prefixos_por_asn(28571)
    assert "200.0.0.0/20" in v4
    assert "2001:db8::/32" in v6


def test_buscar_prefixos_ripe_deduplicates_subnets():
    mock_resp = _make_ripe_mock(["10.0.0.0/20", "10.0.0.0/24"])
    with patch("urllib.request.urlopen", return_value=mock_resp):
        v4, _ = buscar_prefixos_por_asn(28571)
    assert "10.0.0.0/20" in v4
    assert "10.0.0.0/24" not in v4


def test_buscar_prefixos_ripe_fail_fallback_to_irr():
    sock = MagicMock()
    sock.recv.side_effect = [b"200.0.0.0/20\n", b""]
    sock.__enter__ = MagicMock(return_value=sock)
    sock.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", side_effect=Exception("network timeout")):
        with patch("socket.create_connection", return_value=sock):
            v4, v6 = buscar_prefixos_por_asn(28571)

    assert "200.0.0.0/20" in v4
