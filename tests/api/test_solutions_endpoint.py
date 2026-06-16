def test_list_solutions(client):
    res = client.get("/api/solutions")
    assert res.status_code == 200
    data = res.json()
    assert [d["level"] for d in data] == [1, 2, 3]
    assert data[0]["status"] == "available"
    assert data[1]["status"] == "coming_soon"


def test_whoami_and_audit_health(client):
    assert client.get("/api/_internal/whoami").json()["subject"] == "guest"
    assert client.get("/api/_internal/audit/health").json()["mode"] in ("noop", "file")
