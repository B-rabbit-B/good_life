"""删除账号与清空对话：双用户逐表核对、密码复核与勾选确认、令牌与授权失效、磁盘无残留、日志不带内容。"""

import logging
import os
import shutil
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import text

from app.db import get_engine
from app.sdk import AgentGrantToken, GoodLife, SdkError
from tests.agent_fake import scripted  # noqa: F401
from tests.amap_fake import fake  # noqa: F401
from tests.db_inspect import row_counts, user_fingerprint, user_tables
from tests.full_user import evidence_canary, fill_every_table
from tests.helpers import ready_user

PASSWORD = "secret-pass-1"  # tests/helpers.py 注册时用的密码
BACKEND = Path(__file__).resolve().parents[1]
WATCHED = (BACKEND / "app", BACKEND / "migrations")
CONVERSATION_TABLES = ("agent_conversations", "agent_messages", "agent_openings")


def _user_id(username: str) -> str:
    with get_engine().connect() as conn:
        return str(conn.execute(text("SELECT id FROM users WHERE username = :u"), {"u": username}).scalar_one())


def _delete(client, headers, password=PASSWORD, confirm=True):
    return client.post("/api/account/delete", json={"password": password, "confirm": confirm}, headers=headers)


def _error(response) -> tuple[int, str]:
    return response.status_code, response.json()["error"]["code"]


def test_delete_account_removes_every_row_of_that_user_only(client, scripted, fake):  # noqa: F811
    alice = ready_user(client, "alice")
    fill_every_table(client, alice, marker="mkalice01", scripted=scripted, amap=fake)
    bella = ready_user(client, "bella")
    fill_every_table(client, bella, marker="mkbella01", scripted=scripted, amap=fake)
    alice_id, bella_id = _user_id("alice"), _user_id("bella")
    assert all(count > 0 for count in row_counts(alice_id).values())
    bella_counts, bella_print = row_counts(bella_id), user_fingerprint(bella_id)

    response = _delete(client, alice)
    assert response.status_code == 204, response.text
    assert response.content == b""

    counts = row_counts(alice_id)
    assert set(counts) == {"users", *user_tables()}
    assert {table: count for table, count in counts.items() if count} == {}
    assert row_counts(bella_id) == bella_counts
    assert user_fingerprint(bella_id) == bella_print


def test_delete_needs_password_and_confirmation(client):
    headers = ready_user(client, "alice")
    alice_id = _user_id("alice")
    before = user_fingerprint(alice_id)

    assert _error(_delete(client, headers, password="wrong-pass-9")) == (403, "password_incorrect")
    assert _delete(client, headers, password="wrong-pass-9").json()["error"]["message"] == "密码不正确，请重新输入"
    unconfirmed = _delete(client, headers, confirm=False)
    assert _error(unconfirmed) == (422, "validation_error")
    assert unconfirmed.json()["error"]["details"][0]["message"] == "请勾选确认后再删除"
    assert client.post("/api/account/delete", json={"confirm": True}, headers=headers).status_code == 422
    extra = client.post("/api/account/delete", json={"password": PASSWORD, "confirm": True, "user_id": alice_id},
                        headers=headers)
    assert extra.status_code == 422
    assert client.post("/api/account/delete", json={"password": PASSWORD, "confirm": True}).status_code == 401

    assert user_fingerprint(alice_id) == before
    assert client.get("/api/auth/me", headers=headers).status_code == 200


def test_tokens_and_grants_stop_working_after_delete(client):
    headers = ready_user(client, "alice")
    token = client.post("/api/agent-grants", json={"name": "外部", "access": "read"}, headers=headers).json()["token"]
    sdk = GoodLife()
    assert sdk.call(AgentGrantToken(token), "profile.get_capabilities", client_name="pytest").data

    assert _delete(client, headers).status_code == 204
    assert _error(client.get("/api/auth/me", headers=headers)) == (401, "invalid_token")
    assert _error(client.get("/api/profile", headers=headers)) == (401, "invalid_token")
    with pytest.raises(SdkError) as caught:
        sdk.call(AgentGrantToken(token), "profile.get_capabilities", client_name="pytest")
    assert (caught.value.kind, caught.value.code) == ("unauthenticated", "invalid_grant")
    login = client.post("/api/auth/login", json={"username": "alice", "password": PASSWORD})
    assert _error(login) == (401, "invalid_credentials")


def _files(root: Path) -> set[Path]:
    return {path for path in root.rglob("*") if path.is_file() and "__pycache__" not in path.parts}


def test_no_files_left_on_disk_after_upload_and_delete(client, scripted, fake, monkeypatch):  # noqa: F811
    spool = Path(tempfile.mkdtemp(prefix="goodlife-delete-"))
    try:
        monkeypatch.setattr(tempfile, "tempdir", str(spool))
        for name in ("TEMP", "TMP", "TMPDIR"):
            monkeypatch.setenv(name, str(spool))
        created: list[str] = []
        original = tempfile.TemporaryFile

        def recording(*args, **kwargs):  # 记下 multipart 溢出到磁盘时建的临时文件，证明上传确实落过盘
            handle = original(*args, **kwargs)
            created.append(str(getattr(handle, "name", "")))
            return handle

        monkeypatch.setattr(tempfile, "TemporaryFile", recording)
        before = {root: _files(root) for root in WATCHED}

        headers = ready_user(client, "alice")
        marker = "mkdisk01"
        fill_every_table(client, headers, marker=marker, scripted=scripted, amap=fake)
        assert len(created) >= 2  # 医嘱原件与照片各溢出一次
        if os.name == "nt":
            assert all(Path(name).parent == spool for name in created), created
        exported = client.post("/api/account/export", json={"password": PASSWORD}, headers=headers)
        assert exported.status_code == 200, exported.text
        assert _delete(client, headers).status_code == 204

        assert list(spool.iterdir()) == []
        canary = evidence_canary(marker)
        for root in WATCHED:
            after = _files(root)
            assert after - before[root] == set(), root
            assert [path for path in after if canary in path.read_bytes()] == []
    finally:
        shutil.rmtree(spool, ignore_errors=True)


def test_clear_all_conversations_also_clears_openings(client, scripted, fake):  # noqa: F811
    alice = ready_user(client, "alice")
    fill_every_table(client, alice, marker="mkalice02", scripted=scripted, amap=fake)
    bella = ready_user(client, "bella")
    fill_every_table(client, bella, marker="mkbella02", scripted=scripted, amap=fake)
    alice_id, bella_id = _user_id("alice"), _user_id("bella")
    before = row_counts(alice_id)
    assert all(before[table] > 0 for table in CONVERSATION_TABLES)
    bella_print = user_fingerprint(bella_id)

    response = client.delete("/api/agent/conversations", headers=alice)
    assert response.status_code == 204, response.text

    after = row_counts(alice_id)
    assert [after[table] for table in CONVERSATION_TABLES] == [0, 0, 0]
    unchanged = {table: count for table, count in before.items() if table not in CONVERSATION_TABLES}
    assert {table: after[table] for table in unchanged} == unchanged  # 偏好、设置与其余模块都还在
    assert user_fingerprint(bella_id) == bella_print
    assert client.get("/api/agent/conversations", headers=alice).json() == []
    assert len(client.get("/api/agent/preferences", headers=alice).json()) == 1

    again = client.get("/api/agent/opening", headers=alice).json()["opening"]
    assert again is not None and again["kind"] == "review_due"
    assert client.delete("/api/agent/conversations").status_code == 401


def test_export_and_delete_logs_carry_no_content(client, scripted, fake, caplog):  # noqa: F811
    username, marker = "loguser7", "mklogs01"
    headers = ready_user(client, username)
    fill_every_table(client, headers, marker=marker, scripted=scripted, amap=fake)
    caplog.clear()
    caplog.set_level(logging.DEBUG)

    assert client.post("/api/account/export", json={"password": "wrong-pass-9"}, headers=headers).status_code == 403
    assert client.post("/api/account/export", json={"password": PASSWORD}, headers=headers).status_code == 200
    assert _delete(client, headers, confirm=False).status_code == 422
    assert _delete(client, headers).status_code == 204

    logged = caplog.text
    assert "账号导出完成" in logged and "账号已删除" in logged
    for secret in (marker, username, PASSWORD, "wrong-pass-9", headers["Authorization"].removeprefix("Bearer ")):
        assert secret not in logged, secret
