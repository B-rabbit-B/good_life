def register_and_login(client, username: str, password: str = "secret-pass-1") -> dict[str, str]:
    response = client.post("/api/auth/register",
                           json={"username": username, "password": password, "age_confirmed": True})
    assert response.status_code == 201, response.text
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def accept_disclaimer(client, headers: dict[str, str]) -> None:
    version = client.get("/api/disclaimer").json()["version"]
    response = client.post("/api/disclaimer/accept", json={"version": version}, headers=headers)
    assert response.status_code == 200, response.text


def grant_consents(client, headers: dict[str, str], kinds=("cycle", "medical")) -> None:
    """给出经期与（或）医嘱的单独同意，版本取接口返回的当前版本。"""
    version = client.get("/api/consents", headers=headers).json()[0]["current_version"]
    for kind in kinds:
        response = client.post(f"/api/consents/{kind}", json={"version": version}, headers=headers)
        assert response.status_code == 200, response.text


def ready_user(client, username: str, profile: dict | None = None, *, consents: bool = True) -> dict[str, str]:
    """注册、登录、确认免责，默认同时给出经期与医嘱两项单独同意；需要未同意状态时传 consents=False。"""
    headers = register_and_login(client, username)
    accept_disclaimer(client, headers)
    if consents:
        grant_consents(client, headers)
    if profile:
        response = client.patch("/api/profile", json=profile, headers=headers)
        assert response.status_code == 200, response.text
    return headers
