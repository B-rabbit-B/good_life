import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.security.crypto import decrypt_value, encrypt_value
from app.security.passwords import hash_password, verify_password
from app.security.tokens import InvalidTokenError, create_access_token, decode_access_token


def test_password_hash_is_not_plaintext_and_verifies():
    hashed = hash_password("my-secret-pass")
    assert hashed != "my-secret-pass"
    assert hashed.startswith("$argon2id$")
    assert verify_password("my-secret-pass", hashed)
    assert not verify_password("wrong-pass", hashed)


def test_verify_password_rejects_garbage_hash():
    assert not verify_password("anything", "not-a-hash")


def test_token_roundtrip():
    user_id = uuid.uuid4()
    claims = decode_access_token(create_access_token(user_id, 3))
    assert claims.user_id == user_id
    assert claims.token_version == 3


def test_expired_token_is_rejected():
    long_ago = datetime.now(UTC) - timedelta(days=365)
    token = create_access_token(uuid.uuid4(), 0, now=long_ago)
    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


def test_tampered_token_is_rejected():
    token = create_access_token(uuid.uuid4(), 0)
    with pytest.raises(InvalidTokenError):
        decode_access_token(token[:-2] + ("aa" if token[-2:] != "aa" else "bb"))


def test_encryption_roundtrip_and_ciphertext_hides_plaintext():
    value = {"health_conditions": "轻度高血压", "height_cm": 172.5}
    token = encrypt_value(value)
    assert "高血压" not in token
    assert "172.5" not in token
    assert decrypt_value(token) == value


def test_encryption_is_randomized():
    assert encrypt_value("同样的内容") != encrypt_value("同样的内容")
