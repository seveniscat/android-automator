"""API 路由测试(使用 FastAPI TestClient,不依赖真机)。"""

from __future__ import annotations

import contextlib
import os
import tempfile

# 用临时 DB,避免污染开发库
_tmp = tempfile.mkdtemp(prefix="automator_api_test_")
os.environ["AUTOMATOR_DB_URL"] = f"sqlite:///{_tmp}/test.db"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@contextlib.asynccontextmanager
async def _noop_lifespan(app):
    """跳过 lifespan(避免在测试里启 scheduler / 连真机)。"""
    yield


@pytest.fixture(scope="module")
def client():
    from automator.main import create_app

    app = create_app()
    app.router.lifespan_context = _noop_lifespan
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/api/system/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_env(client):
    r = client.get("/api/system/env")
    assert r.status_code == 200
    data = r.json()
    assert "click" in data["available_steps"]


def test_flow_validate_ok(client):
    r = client.post(
        "/api/flows/validate",
        json={"yaml": "name: t\nsteps:\n  - wait: { seconds: 1 }"},
    )
    assert r.status_code == 200
    assert r.json()["valid"] is True


def test_flow_validate_bad(client):
    r = client.post(
        "/api/flows/validate",
        json={"yaml": "name: t\nsteps:\n  - __bad__: {}"},
    )
    assert r.json()["valid"] is False


def test_flow_crud(client):
    r = client.post(
        "/api/flows",
        json={
            "name": "测试流程",
            "yaml": "name: 测试流程\nsteps:\n  - wait: { seconds: 1 }",
        },
    )
    assert r.status_code == 200
    fid = r.json()["id"]

    r = client.get("/api/flows")
    assert any(f["id"] == fid for f in r.json()["items"])

    r = client.get(f"/api/flows/{fid}")
    assert r.json()["name"] == "测试流程"

    r = client.delete(f"/api/flows/{fid}")
    assert r.status_code == 200


def test_steps_list(client):
    r = client.get("/api/flows/steps/list")
    assert "click" in r.json()["steps"]
