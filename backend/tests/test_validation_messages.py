"""参数校验的说明按错误类型换成中文（界面文字全部是中文）；原始英文说明与类型留在 details 里供排查。"""

import uuid
from datetime import date, datetime
from typing import Any, Literal

import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.errors import VALIDATION_FALLBACK, validation_message


class _Sample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=3, max_length=5, pattern=r"^[a-z]+$")
    count: int = 0
    weight: float = Field(default=50, ge=20, le=300)
    ratio: float = Field(default=1, gt=0, lt=2)
    gender: Literal["female", "male", "other"] = "female"
    day: date | None = None
    at: datetime | None = None
    ref: uuid.UUID | None = None
    flag: bool = False
    tags: list[str] = Field(default_factory=list, max_length=2)
    year: int = 2000

    @field_validator("year")
    @classmethod
    def not_future(cls, value: int) -> int:
        if value > 2100:
            raise ValueError("出生年份不能晚于今年")
        if value < 0:
            raise ValueError("must be positive")
        return value


def _errors(payload: dict[str, Any]) -> list[dict[str, Any]]:
    with pytest.raises(ValidationError) as caught:
        _Sample.model_validate(payload)
    return caught.value.errors()


def _only(payload: dict[str, Any], kind: str) -> dict[str, Any]:
    errors = [err for err in _errors({"name": "abc", **payload}) if err["type"] == kind]
    assert len(errors) == 1, errors
    return errors[0]


@pytest.mark.parametrize("payload, kind, message", [
    ({"name": None}, "string_type", "应填写文字"),
    ({"name": "ab"}, "string_too_short", "至少 3 个字符，请补全"),
    ({"name": "abcdef"}, "string_too_long", "最多 5 个字符，请删减"),
    ({"name": "ab1"}, "string_pattern_mismatch", "格式不符合要求，请按提示修改"),
    ({"count": "x"}, "int_parsing", "请填写整数"),
    ({"count": 1.5}, "int_from_float", "请填写整数"),
    ({"count": []}, "int_type", "请填写整数"),
    ({"weight": "abc"}, "float_parsing", "请填写数字"),
    ({"weight": 10}, "greater_than_equal", "不能小于 20"),
    ({"weight": 301}, "less_than_equal", "不能大于 300"),
    ({"ratio": 0}, "greater_than", "必须大于 0"),
    ({"ratio": 2}, "less_than", "必须小于 2"),
    ({"gender": "x"}, "literal_error", "只能从这些选项中选：female、male、other"),
    ({"year": 2200}, "value_error", "出生年份不能晚于今年"),
    ({"year": -1}, "value_error", VALIDATION_FALLBACK),
    ({"extra": 1}, "extra_forbidden", "不能提交这一项，请去掉后重试"),
    ({"day": "10/12"}, "date_from_datetime_parsing", "日期格式不对，请按“年-月-日”填写，例如 2026-10-12"),
    ({"at": "later"}, "datetime_from_date_parsing", "时间格式不对，请按“年-月-日 时:分”填写"),
    ({"ref": "not-a-uuid"}, "uuid_parsing", "编号格式不对，请重新选择"),
    ({"flag": "maybe"}, "bool_parsing", "只能是“是”或“否”"),
    ({"tags": ["a", "b", "c"]}, "too_long", "最多 2 项，请删去一些"),
])
def test_each_covered_type_gets_a_chinese_message(payload, kind, message):
    assert validation_message(_only(payload, kind)) == message


def test_missing_and_one_character_minimum():
    missing = [err for err in _errors({}) if err["type"] == "missing"]
    assert [validation_message(err) for err in missing] == ["这一项必须填写"]
    assert validation_message({"type": "string_too_short", "ctx": {"min_length": 1}}) == "不能为空，请填写"


@pytest.mark.parametrize("kind", ["date_parsing", "datetime_parsing", "enum", "float_type", "bool_type", "uuid_type"])
def test_related_types_share_the_message(kind):
    assert validation_message({"type": kind, "ctx": {"expected": "'a' or 'b'"}}) != VALIDATION_FALLBACK


def test_unknown_type_falls_back():
    assert validation_message({"type": "url_parsing", "msg": "Input should be a valid URL"}) == VALIDATION_FALLBACK
    assert validation_message({}) == VALIDATION_FALLBACK


def test_login_with_a_short_password_returns_chinese_details(client):
    response = client.post("/api/auth/register", json={"username": "alice", "password": "short", "age_confirmed": True})
    assert response.status_code == 422
    error = response.json()["error"]
    assert (error["code"], error["message"]) == ("validation_error", "请求参数不合法")
    assert error["details"] == [{
        "field": "password",
        "message": "至少 8 个字符，请补全",
        "type": "string_too_short",
        "original": "String should have at least 8 characters",
    }]


def test_profile_number_text_is_rejected_in_chinese(client):
    client.post("/api/auth/register", json={"username": "bob", "password": "secret-pass-1", "age_confirmed": True})
    token = client.post("/api/auth/login", json={"username": "bob", "password": "secret-pass-1"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    version = client.get("/api/disclaimer").json()["version"]
    client.post("/api/disclaimer/accept", json={"version": version}, headers=headers)
    response = client.patch("/api/profile", json={"height_cm": "", "weight_kg": "abc"}, headers=headers)
    assert response.status_code == 422
    assert {d["field"]: d["message"] for d in response.json()["error"]["details"]} == {
        "height_cm": "请填写数字", "weight_kg": "请填写数字",
    }
