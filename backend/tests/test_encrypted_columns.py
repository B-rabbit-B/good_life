"""加密列核对：填满全部业务表后，直接读数据库里的原始列值，逐列确认存的是密文（列清单按模型现算）。

安全审查记录的“加密列逐列表”以这份清单为准；新增加密列而没有被填上数据，这里会失败，提醒补充夹具。
"""

from sqlalchemy import text

import app.models  # noqa: F401
from app.db import Base, get_engine
from app.security.crypto import EncryptedBytes, EncryptedJSON
from tests.agent_fake import scripted  # noqa: F401
from tests.amap_fake import fake  # noqa: F401
from tests.full_user import fill_every_table
from tests.helpers import ready_user

MARKER = "mkcipher01"
FERNET_PREFIX = b"gAAAA"  # Fernet 令牌的版本字节经 base64 后固定以此开头


def encrypted_columns() -> list[tuple[str, str]]:
    return sorted((table.name, column.name) for table in Base.metadata.tables.values() for column in table.columns
                  if isinstance(column.type, (EncryptedJSON, EncryptedBytes)))


def _raw(value) -> bytes:
    return value.encode("utf-8") if isinstance(value, str) else bytes(value)


def test_the_model_still_has_at_least_the_known_encrypted_columns():
    """只守下界，防止列清单被悄悄扫空；具体是哪些列由安全审查记录的逐列表与文档测试按集合核对。"""
    columns = encrypted_columns()
    assert len(columns) >= 26
    assert len({table for table, _column in columns}) >= 17


def test_every_encrypted_column_holds_only_ciphertext_after_every_table_is_filled(client, scripted, fake):  # noqa: F811
    headers = ready_user(client, "alice")
    ids = fill_every_table(client, headers, marker=MARKER, scripted=scripted, amap=fake)
    # 夹具没有写解除原因，这里补一步提出解除建议，让该列也有数据
    proposal = client.post(f"/api/medical/items/{ids['item_id']}/propose-resolution", headers=headers,
                           json={"reason": f"解除原因{MARKER}"})
    assert proposal.status_code == 200, proposal.text
    unfilled = []
    with get_engine().connect() as conn:
        for table, column in encrypted_columns():
            values = list(conn.execute(text(f'SELECT "{column}" FROM "{table}" WHERE "{column}" IS NOT NULL')).scalars())
            if not values:
                unfilled.append(f"{table}.{column}")
            for value in values:
                raw = _raw(value)
                assert raw.startswith(FERNET_PREFIX), (table, column)
                assert MARKER.encode() not in raw, (table, column)
    assert unfilled == [], unfilled
