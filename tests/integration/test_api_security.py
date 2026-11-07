"""API authentication, CORS, and council-size limits."""

import os
import stat

import httpx
import pytest

from backend import main, security

TOKEN = "security-test-token"


@pytest.fixture
async def client(monkeypatch, tmp_path):
    monkeypatch.setenv(security.API_TOKEN_ENV, TOKEN)
    monkeypatch.setattr(main.storage, "DATA_DIR", str(tmp_path))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=main.app), base_url="http://test"
    ) as c:
        yield c


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/conversations"),
        ("DELETE", "/api/conversations?confirm=true"),
        ("PUT", "/api/council/config"),
        ("POST", "/api/conversations/abc/message/stream"),
        ("GET", "/api/debug/config"),
    ],
)
@pytest.mark.parametrize(
    "auth", [None, "Bearer wrong-token", TOKEN], ids=["missing", "wrong", "no-scheme"]
)
async def test_api_routes_require_bearer_token(client, method, path, auth):
    headers = {"Authorization": auth} if auth else {}
    response = await client.request(method, path, headers=headers)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


async def test_valid_token_is_accepted(client):
    response = await client.get(
        "/api/conversations", headers={"Authorization": f"Bearer {TOKEN}"}
    )
    assert response.status_code == 200


async def test_health_check_is_public(client):
    assert (await client.get("/")).status_code == 200


async def test_cors_rejects_untrusted_origin(client):
    response = await client.options(
        "/api/conversations",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


async def test_cors_allows_configured_frontend_origin(client):
    response = await client.options(
        "/api/conversations",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_origins_from_env(monkeypatch):
    monkeypatch.setenv(
        security.CORS_ORIGINS_ENV, "http://192.168.1.5:5173/, https://council.lan"
    )
    assert security.get_cors_origins() == [
        "http://192.168.1.5:5173",
        "https://council.lan",
    ]


def test_cors_wildcard_is_rejected(monkeypatch):
    monkeypatch.setenv(security.CORS_ORIGINS_ENV, "*")
    with pytest.raises(RuntimeError):
        security.get_cors_origins()


def test_generated_token_is_persisted_with_private_permissions(monkeypatch, tmp_path):
    token_file = tmp_path / "data" / "api_token"
    monkeypatch.delenv(security.API_TOKEN_ENV, raising=False)
    monkeypatch.setattr(security, "API_TOKEN_FILE", str(token_file))
    monkeypatch.setattr(security, "_generated_token", None)

    token = security.get_api_token()

    assert len(token) >= 32
    assert token_file.read_text().strip() == token
    assert stat.S_IMODE(os.stat(token_file).st_mode) == 0o600
    monkeypatch.setattr(security, "_generated_token", None)
    assert security.get_api_token() == token


def test_login_link_contains_encoded_token(monkeypatch, tmp_path):
    url_file = tmp_path / "data" / "api_url"
    monkeypatch.setenv(security.API_TOKEN_ENV, "a+b&c#d")
    monkeypatch.setattr(security, "API_URL_FILE", str(url_file))
    monkeypatch.setattr(security, "_generated_token", None)

    path = security.write_login_link("http://localhost:5173")

    assert path == str(url_file)
    link = url_file.read_text().strip()
    assert link == "http://localhost:5173/?token=a%2Bb%26c%23d"
    assert stat.S_IMODE(os.stat(url_file).st_mode) == 0o600


async def test_council_size_is_capped(client):
    models = [f"provider/model-{i}" for i in range(security.MAX_COUNCIL_MODELS + 1)]
    response = await client.put(
        "/api/council/config",
        headers={"Authorization": f"Bearer {TOKEN}"},
        json={"council_models": models, "chairman_model": "provider/chair"},
    )
    assert response.status_code == 400
    assert "At most" in response.json()["detail"]
