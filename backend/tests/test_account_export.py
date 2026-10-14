"""导出我的数据：密码复核、压缩包结构、与各读取接口逐项一致、原件与照片、不含哈希令牌密钥与他人数据、不缓存且有审计。"""

import io
import json
import re
import zipfile
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select, text

from app.account.export import EXPORT_FILES, README_NAME
from app.agent.models import AgentMessage, AgentOpening
from app.db import get_engine, get_sessionmaker
from tests.agent_fake import SECRET, scripted  # noqa: F401
from tests.amap_fake import fake  # noqa: F401
from tests.full_user import fill_every_table
from tests.helpers import ready_user

PASSWORD = "secret-pass-1"  # tests/helpers.py 注册时用的密码
MARK = "mkowner01"
OTHER_MARK = "mkother01"
UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
ENTRY_NAME = re.compile(rf"^(?:[a-z_]+\.json|说明\.txt|evidence/{UUID}\.(?:jpg|png|webp|pdf)|photos/{UUID}\.jpg)$")


@pytest.fixture
def owner(client, scripted, fake):  # noqa: F811
    headers = ready_user(client, "owner")
    ids = fill_every_table(client, headers, marker=MARK, scripted=scripted, amap=fake)
    return headers, ids


def _export(client, headers, password=PASSWORD):
    return client.post("/api/account/export", json={"password": password}, headers=headers)


def _unzip(response) -> dict[str, bytes]:
    assert response.status_code == 200, response.text
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert archive.testzip() is None
        assert all(info.compress_type == zipfile.ZIP_DEFLATED for info in archive.infolist())
        return {name: archive.read(name) for name in archive.namelist()}


def _json(entries: dict[str, bytes], name: str):
    return json.loads(entries[name].decode("utf-8"))


def _get(client, headers, path, **params):
    response = client.get(path, headers=headers, params=params)
    assert response.status_code == 200, (path, response.text)
    return response.json()


def _audits(client, headers):
    return _get(client, headers, "/api/agent-grants/audit", limit=200)


def test_export_needs_the_password(client):
    headers = ready_user(client, "owner")
    wrong = _export(client, headers, "wrong-pass-9")
    assert wrong.status_code == 403
    assert wrong.json()["error"] == {"code": "password_incorrect", "message": "密码不正确，请重新输入"}
    assert client.post("/api/account/export", json={}, headers=headers).status_code == 422
    assert client.post("/api/account/export", json={"password": ""}, headers=headers).status_code == 422
    assert client.post("/api/account/export", json={"password": "x" * 129}, headers=headers).status_code == 422
    assert client.post("/api/account/export", json={"password": PASSWORD, "x": 1}, headers=headers).status_code == 422
    assert client.post("/api/account/export", json={"password": PASSWORD}).status_code == 401
    assert _audits(client, headers) == []  # 失败的导出不记审计


def test_export_is_a_zip_with_one_file_per_module_and_a_readme(client, owner):
    headers, ids = owner
    response = _export(client, headers)
    entries = _unzip(response)
    assert response.headers["content-type"] == "application/zip"
    today = date.today().strftime("%Y%m%d")
    assert response.headers["content-disposition"] == f'attachment; filename="good-life-export-{today}.zip"'
    assert set(entries) == {*EXPORT_FILES, README_NAME, f"evidence/{ids['evidence_id']}.pdf",
                            f"photos/{ids['rec_id']}.jpg"}
    assert len(EXPORT_FILES) == 13
    assert [name for name in entries if not ENTRY_NAME.match(name)] == []
    for name in EXPORT_FILES:
        raw = entries[name].decode("utf-8")
        assert raw.startswith("{\n  \"")  # 缩进 2
        assert "\\u" not in raw  # 中文不转义
    readme = entries[README_NAME].decode("utf-8")
    for phrase in ("密钥只含掩码", "不含密码与授权令牌", "对话里可能有其他模块数据的副本", *EXPORT_FILES, "evidence", "photos"):
        assert phrase in readme, phrase


def test_export_matches_every_read_endpoint(client, owner):
    headers, ids = owner
    get = lambda path, **params: _get(client, headers, path, **params)  # noqa: E731
    today = date.today()
    conversations = get("/api/agent/conversations")
    providers = get("/api/llm/providers")
    recognitions = get("/api/photos/recognitions")
    sample = {
        "account": get("/api/auth/me"),
        "profile": {"profile": get("/api/profile"), "changes": get("/api/profile/changes")},
        "cycle": {"periods": get("/api/cycle/periods"),
                  "day_logs": get("/api/cycle/day-logs", start="2000-01-01", end=today.isoformat()),
                  "settings": get("/api/cycle/settings")},
        "medical": {"orders": get("/api/medical/orders"), "items": get("/api/medical/items"),
                    "events": get("/api/medical/events", limit=200)},
        "nutrition": {"meals": get("/api/nutrition/meals", date=today.isoformat())},
        "fitness": {"workouts": get("/api/fitness/workouts", start=(today - timedelta(days=365)).isoformat(),
                                    end=today.isoformat()),
                    "custom_exercises": get("/api/fitness/exercises/custom")},
        "conversations": [get(f"/api/agent/conversations/{c['id']}") for c in conversations],
        "preferences": get("/api/agent/preferences"),
        "agent_settings": get("/api/agent/settings"),
        "photos": [get(f"/api/photos/recognitions/{r['id']}") for r in recognitions],
        "llm": {"providers": providers,
                "models": [m for p in providers for m in get(f"/api/llm/providers/{p['id']}/models")],
                "assignments": get("/api/llm/assignments")},
        "agent_grants": {"grants": get("/api/agent-grants"), "audits": _audits(client, headers)},
        "restaurants": {"settings": get("/api/restaurants/settings")},
        "disclaimer": get("/api/disclaimer/status"),
        "consents": get("/api/consents"),
    }
    sampled_at = datetime.now(UTC)
    entries = _unzip(_export(client, headers))

    assert _json(entries, "account.json") == sample["account"]
    assert _json(entries, "profile.json") == sample["profile"]
    assert _json(entries, "cycle.json") == sample["cycle"]
    assert _json(entries, "medical.json") == sample["medical"]
    assert _json(entries, "nutrition.json") == sample["nutrition"]
    assert _json(entries, "fitness.json") == sample["fitness"]
    assert len(sample["fitness"]["workouts"]) == 1 and len(sample["nutrition"]["meals"]) == 1

    exported_conversations = _json(entries, "conversations.json")["conversations"]
    assert [{k: v for k, v in c.items() if k != "transcript"} for c in exported_conversations] == \
        sample["conversations"]
    preferences = _json(entries, "preferences_and_openings.json")
    assert preferences["preferences"] == sample["preferences"]
    assert preferences["settings"] == sample["agent_settings"]
    assert _json(entries, "photos.json") == {"recognitions": sample["photos"]}
    assert _json(entries, "llm.json") == sample["llm"]
    assert _json(entries, "restaurants.json") == sample["restaurants"]
    consents = _json(entries, "disclaimer_and_consents.json")
    assert consents["disclaimer"] == sample["disclaimer"] and consents["consents"] == sample["consents"]
    assert [row["version"] for row in consents["disclaimer_acceptances"]] == [sample["disclaimer"]["current_version"]]

    # 审计：导出里的审计就是导出之前的全部审计；导出之后接口多出恰好一行导出自身的 account.export
    grants = _json(entries, "agent_grants.json")
    assert grants == sample["agent_grants"]
    after = _audits(client, headers)
    own = [row for row in after if row["capability"] == "account.export"
           and datetime.fromisoformat(row["created_at"]) > sampled_at]
    assert len(own) == 1
    assert [row for row in after if row not in own] == grants["audits"]

    # 接口没有的部分与数据库比较：对话的工具调用与工具结果、开场记录
    with get_sessionmaker()() as db:
        stored = list(db.scalars(select(AgentMessage).where(AgentMessage.conversation_id == ids["conversation_id"])
                                 .order_by(AgentMessage.position)))
        openings = list(db.scalars(select(AgentOpening).order_by(AgentOpening.created_at)))
        [transcript] = [c["transcript"] for c in exported_conversations]
        assert [(m["id"], m["position"], m["role"]) for m in transcript] == \
            [(str(m.id), m.position, m.role) for m in stored]
        for exported, row in zip(transcript, stored, strict=True):
            expected = {k: v for k, v in row.content.items() if k != "provider_state"}
            if "tool_calls" in expected:
                expected["tool_calls"] = [{k: v for k, v in c.items() if k != "provider_state"}
                                          for c in expected["tool_calls"]]
            assert {k: v for k, v in exported.items() if k not in ("id", "position", "role", "created_at")} == expected
        tools = [m for m in transcript if m["role"] == "tool"]
        assert [m["tool_name"] for m in tools] == ["cycle_record_period"] and tools[0]["text"]
        assert [m["tool_calls"][0]["name"] for m in transcript if m.get("tool_calls")] == ["cycle_record_period"]
        assert [{**o, "created_at": datetime.fromisoformat(o["created_at"])} for o in preferences["openings"]] == [
            {"id": str(o.id), "day": o.day.isoformat(), "kind": o.kind, "status": o.status, "question": o.question,
             "created_at": o.created_at} for o in openings]
        assert openings and MARK in openings[0].question
    assert "provider_state" not in entries["conversations.json"].decode("utf-8")


def test_export_has_evidence_and_kept_photos_under_generated_names(client, owner):
    headers, ids = owner
    entries = _unzip(_export(client, headers))
    evidence = client.get(f"/api/medical/evidence/{ids['evidence_id']}", headers=headers)
    assert entries[f"evidence/{ids['evidence_id']}.pdf"] == evidence.content
    image = client.get(f"/api/photos/recognitions/{ids['rec_id']}/image", headers=headers)
    assert entries[f"photos/{ids['rec_id']}.jpg"] == image.content
    original = f"原件-{MARK}.pdf".encode()
    assert [name for name, data in entries.items() if original in data] == ["medical.json"]


def test_export_has_no_hashes_tokens_keys_or_other_users(client, owner, scripted, fake):  # noqa: F811
    headers, ids = owner
    other = ready_user(client, "bystander")
    other_ids = fill_every_table(client, other, marker=OTHER_MARK, scripted=scripted, amap=fake)
    entries = _unzip(_export(client, headers))
    with get_engine().connect() as conn:
        password_hash = conn.execute(text("SELECT password_hash FROM users WHERE username = 'owner'")).scalar_one()
        token_hashes = conn.execute(text("SELECT token_hash FROM agent_grants")).scalars().all()
    blob = b"\n".join(entries.values())
    assert MARK.encode() in blob
    forbidden = ["password_hash", "token_hash", "token_version", "api_key", SECRET, password_hash, *token_hashes,
                 ids["grant_token"], other_ids["grant_token"], OTHER_MARK, "bystander", PASSWORD,
                 headers["Authorization"].removeprefix("Bearer ")]
    assert [value for value in forbidden if value.encode() in blob] == []
    assert all(other_ids[key] not in blob.decode("utf-8", "ignore") for key in other_ids if key.endswith("_id"))
    llm = _json(entries, "llm.json")
    assert [provider["key_hint"] for provider in llm["providers"]] and "key_hint" in entries["llm.json"].decode()


def test_export_response_is_not_cacheable_and_audited(client, owner):
    headers, _ = owner
    before = _audits(client, headers)
    response = _export(client, headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    after = _audits(client, headers)
    assert len(after) == len(before) + 1
    [row] = [row for row in after if row not in before]
    assert (row["capability"], row["credential_kind"], row["client_name"], row["outcome"], row["grant_id"]) == \
        ("account.export", "user_session", "app", "ok", None)
