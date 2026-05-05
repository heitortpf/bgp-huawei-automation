import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from bgp.models import RouterConfig


# --- Auth ---

def test_login_success(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test_secret_key_at_least_32_chars_long")
    with patch("api.routers.auth.verificar_credenciais", return_value=True):
        from api.app import app
        with TestClient(app) as c:
            resp = c.post("/api/auth/login", json={"username": "admin", "password": "any"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()
    assert resp.json()["token_type"] == "bearer"


def test_login_wrong_password(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test_secret_key_at_least_32_chars_long")
    with patch("api.routers.auth.verificar_credenciais", return_value=False):
        from api.app import app
        with TestClient(app) as c:
            resp = c.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401


# --- Sessão: preview ---

def test_preview_valid(client):
    resp = client.post("/api/sessao/preview", json={
        "sessao": {
            "local_as": 65001,
            "neighbor_ip": "10.0.0.1",
            "neighbor_as": 28571,
            "nome_cliente": "TESTE",
            "prefixes_ipv4": ["200.0.0.0/20"],
            "prefixes_ipv6": [],
        }
    })
    assert resp.status_code == 200
    cmds = resp.json()["comandos"]
    assert len(cmds) > 0
    assert cmds[0] == "system-view"
    assert cmds[-1] == "return"


def test_preview_invalid_ip(client):
    resp = client.post("/api/sessao/preview", json={
        "sessao": {
            "local_as": 65001,
            "neighbor_ip": "not-an-ip",
            "neighbor_as": 28571,
            "nome_cliente": "TESTE",
        }
    })
    assert resp.status_code == 422


def test_preview_invalid_prefix(client):
    resp = client.post("/api/sessao/preview", json={
        "sessao": {
            "local_as": 65001,
            "neighbor_ip": "10.0.0.1",
            "neighbor_as": 28571,
            "nome_cliente": "TESTE",
            "prefixes_ipv4": ["not-a-prefix"],
        }
    })
    assert resp.status_code == 422


# --- Roteadores ---

def test_roteadores_list_empty(client):
    from bgp.exceptions import RouterInventoryError
    with patch("api.routers.roteadores.ler_routers_txt", side_effect=RouterInventoryError("no file")):
        resp = client.get("/api/roteadores")
    assert resp.status_code == 200
    assert resp.json() == []


def test_roteadores_add_and_delete(client, tmp_routers_file):
    import bgp.router_io as rio

    with (
        patch("api.routers.roteadores.ler_routers_txt", lambda: rio.ler_routers_txt(tmp_routers_file)),
        patch("api.routers.roteadores.acrescentar_router", lambda r: rio.acrescentar_router(r, tmp_routers_file)),
        patch("api.routers.roteadores.remover_router", lambda host: rio.remover_router(host, tmp_routers_file)),
    ):
        resp = client.post("/api/roteadores", json={
            "host": "10.0.0.2", "username": "admin", "password": "pass", "port": 22
        })
        assert resp.status_code == 201
        assert resp.json()["host"] == "10.0.0.2"

        resp = client.delete("/api/roteadores/10.0.0.2")
        assert resp.status_code == 204

        resp = client.get("/api/roteadores")
        hosts = [r["host"] for r in resp.json()]
        assert "10.0.0.2" not in hosts


def test_roteadores_delete_not_found(client):
    with patch("api.routers.roteadores.remover_router", return_value=False):
        resp = client.delete("/api/roteadores/inexistente")
    assert resp.status_code == 404


# --- Sessão: aplicar edge cases ---

def test_aplicar_empty_roteadores_list(client):
    fake_routers = [RouterConfig(host="10.0.0.1", username="admin", password="pass", port=22)]
    with patch("api.routers.sessao.ler_routers_txt", return_value=fake_routers):
        resp = client.post("/api/sessao/aplicar", json={
            "sessao": {
                "local_as": 65001,
                "neighbor_ip": "10.0.0.1",
                "neighbor_as": 28571,
                "nome_cliente": "TESTE",
            },
            "roteadores": [],
        })
    assert resp.status_code == 400
    assert "roteador" in resp.json()["detail"].lower()


def test_aplicar_unknown_router(client):
    fake_routers = [RouterConfig(host="10.0.0.1", username="admin", password="pass", port=22)]
    with patch("api.routers.sessao.ler_routers_txt", return_value=fake_routers):
        resp = client.post("/api/sessao/aplicar", json={
            "sessao": {
                "local_as": 65001,
                "neighbor_ip": "10.0.0.1",
                "neighbor_as": 28571,
                "nome_cliente": "TESTE",
            },
            "roteadores": ["99.99.99.99"],
        })
    assert resp.status_code == 404
