from fastapi.testclient import TestClient

from lightning.desktop.server import Credentials, probe_app


def client():
    credentials = Credentials("http://127.0.0.1:9876")
    return TestClient(probe_app(credentials, {"synthetic": True}), base_url=credentials.origin), credentials


def test_launch_cookie_is_required_for_every_resource():
    browser, cfg = client()
    for path in ("/", "/api/check", "/static/missing", "/unknown"):
        response = browser.get(path)
        assert response.status_code == 403
        assert response.headers["cache-control"] == "no-store"
    response = browser.get("/__launch", params={"code": cfg.launch_code})
    assert response.status_code == 200 and 'id="probe-ready"' in response.text
    assert browser.get("/api/check").json()["ok"] is True
    assert browser.get("/__launch", params={"code": cfg.launch_code}).status_code == 403


def test_host_origin_and_expired_links_fail_closed():
    browser, cfg = client()
    assert browser.get("/", headers={"host": "localhost:9876"}).status_code == 400
    cfg.expires = 0
    assert browser.get("/__launch", params={"code": cfg.launch_code}).status_code == 403
    browser.cookies.set(cfg.cookie_name, cfg.token)
    for site in ("cross-site", "same-site"):
        assert browser.get("/", headers={"sec-fetch-site": site}).status_code == 403
    assert browser.post("/api/check").status_code == 403
    assert browser.post("/api/check", headers={"origin": "http://127.0.0.1:9000"}).status_code == 403


def test_instances_use_distinct_cookie_names_and_unicode_code_is_rejected():
    browser, cfg = client()
    assert cfg.cookie_name != Credentials(cfg.origin).cookie_name
    assert browser.get("/__launch", params={"code": "é"}).status_code == 403


def test_real_loopback_server_exchanges_cookie_and_stops():
    import httpx
    import socket

    from lightning.desktop.server import LocalServer
    server = LocalServer({"synthetic": True}).start()
    port = server.socket.getsockname()[1]
    try:
        with httpx.Client(follow_redirects=True, trust_env=False) as browser:
            assert browser.get(server.origin).status_code == 403
            assert browser.get(server.launch_url).status_code == 200
            assert browser.get(server.origin + "/api/check").json()["ok"] is True
    finally:
        server.stop()
    assert not server.thread.is_alive()
    with socket.socket() as sock:
        assert sock.connect_ex(("127.0.0.1", port)) != 0
