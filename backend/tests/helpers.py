def register_and_login(client, username: str, password: str = "secret-pass-1") -> dict[str, str]:
    response = client.post("/api/auth/register", json={"username": username, "password": password})
    assert response.status_code == 201, response.text
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def accept_disclaimer(client, headers: dict[str, str]) -> None:
    version = client.get("/api/disclaimer").json()["version"]
    response = client.post("/api/disclaimer/accept", json={"version": version}, headers=headers)
    assert response.status_code == 200, response.text
