import pytest
from fastapi.testclient import TestClient

from agenteval.api import create_app

BASE = "http://127.0.0.1:8765"


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "web.sqlite3"), base_url=BASE) as api:
        yield api


def token(client):
    response = client.get("/api/session")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "access-control-allow-origin" not in response.headers
    assert "set-cookie" not in response.headers
    return response.json()["csrf_token"]


def test_valid_browser_and_script(client):
    csrf = token(client)
    assert len(csrf) >= 43
    for origin in [None, BASE]:
        headers = {"X-CSRF-Token": csrf}
        if origin:
            headers.update({"Origin": origin, "Sec-Fetch-Site": "same-origin"})
        assert client.post("/api/runs", headers=headers).status_code == 201


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"X-CSRF-Token": "wrong"},
        {"X-CSRF-Token": ""},
    ],
)
def test_missing_invalid_token(client, headers):
    response = client.post("/runs", headers=headers)
    assert response.status_code == 403
    assert response.json()["code"] == "csrf_required"
    assert client.get("/runs").json()["run_ids"] == []


@pytest.mark.parametrize(
    "headers,status",
    [
        ({"Origin": "null"}, 403),
        ({"Origin": "https://evil.example"}, 403),
        ({"Origin": "http://localhost:8765"}, 403),
        ({"Origin": "http://127.0.0.1:8766"}, 403),
        ({"Origin": "http://127.0.0.1:5173"}, 403),
        ({"Origin": "http://127.0.0.1:8765/"}, 403),
        ({"Sec-Fetch-Site": "cross-site"}, 403),
        ({"Sec-Fetch-Site": "same-site"}, 403),
        ({"Sec-Fetch-Mode": "no-cors"}, 403),
        ({"Sec-Fetch-Mode": "navigate"}, 403),
        ({"Sec-Fetch-Dest": "image"}, 403),
        ({"Cookie": "session=attacker"}, 403),
        ({"Authorization": "Bearer attacker"}, 403),
        ({"Host": "evil.example:8765"}, 400),
        ({"Host": "localhost:8765"}, 400),
        ({"Host": "127.0.0.1:9999"}, 400),
        ({"Host": "127.0.0.1.evil.example:8765"}, 400),
        ({"X-Forwarded-Host": "evil.example"}, 403),
        ({"Forwarded": "host=evil.example"}, 403),
    ],
)
def test_host_origin_fetch_and_ambient_credentials(client, headers, status):
    csrf = token(client)
    assert client.get("/api/session", headers=headers).status_code == status
    assert client.post("/api/runs", headers={**headers, "X-CSRF-Token": csrf}).status_code == status
    assert client.get("/runs").json()["run_ids"] == []


def test_duplicate_headers_and_preflight(client):
    assert client.get("/session", headers=[("Origin", BASE), ("Origin", "null")]).status_code == 400
    assert (
        client.post(
            "/runs", headers=[("X-CSRF-Token", token(client)), ("X-CSRF-Token", "wrong")]
        ).status_code
        == 400
    )
    response = client.options(
        "/runs", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"}
    )
    assert response.status_code == 403
    assert "access-control-allow-origin" not in response.headers


def test_dev_origin_opt_in_and_token_restart(tmp_path):
    path = tmp_path / "web.sqlite3"
    with TestClient(create_app(path, dev_ui=True), base_url=BASE) as client:
        old = token(client)
        assert (
            client.post(
                "/api/runs", headers={"Origin": "http://127.0.0.1:5173", "X-CSRF-Token": old}
            ).status_code
            == 201
        )
    with TestClient(create_app(path, dev_ui=True), base_url=BASE) as client:
        assert token(client) != old
        assert client.post("/runs", headers={"X-CSRF-Token": old}).status_code == 403


def test_static_ui_has_security_headers_and_no_traversal(tmp_path):
    ui = tmp_path / "ui"
    ui.mkdir()
    (ui / "index.html").write_text("<h1>Local UI</h1>", encoding="utf-8")
    (tmp_path / "private.txt").write_text("PRIVATE", encoding="utf-8")
    with TestClient(create_app(tmp_path / "web.sqlite3", ui_dir=ui), base_url=BASE) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
        assert client.get("/%2e%2e/private.txt").status_code == 404


def test_invalid_configuration(tmp_path):
    with pytest.raises(ValueError):
        create_app(tmp_path / "web.sqlite3", port=80)
    with pytest.raises(ValueError):
        create_app(tmp_path / "web.sqlite3", ui_dir=tmp_path / "missing")
