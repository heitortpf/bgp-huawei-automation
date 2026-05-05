import pytest
from fastapi.testclient import TestClient
from api.app import app
from api.auth import get_current_user


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = lambda: "test_user"
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def tmp_routers_file(tmp_path):
    f = tmp_path / "routers.txt"
    f.write_text("10.0.0.1,admin,senha123,22\n", encoding="utf-8")
    return f
